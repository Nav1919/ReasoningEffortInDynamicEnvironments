# Local Freeway diagnosis — 2026-10-07

All work uses the local Ollama service at `http://localhost:11434`. No paid
APIs, downloaded models, commits, pushes, or GitHub operations were used.
Initial `git status --short` was empty. No applicable AGENTS.md files were
found in the repository or its ancestor directories.

## Evidence and environment audit

The installed RealtimeGym is an editable sibling checkout at
`../RealtimeGym/src/realtimegym`, commit
`3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`, with clean status. The audit read
`environments/freeway.py` and `environments/base.py`; that checkout was not
edited. Ollama `/api/show` confirms Qwen3, 4.0B parameters, GGUF, Q4_K_M.
Full metadata is in `logs/diagnosis_model_metadata.json` and each new run.
The initial sandbox denied localhost access; authorized elevated execution
connected successfully. This was a sandbox restriction, not an Ollama outage.

The exact prompt and observation are saved in every decision's
`request.messages[0].content`. The original prompt is preserved byte for byte
by `build_prompt(..., strategy="original", board="full")`. Observations contain
`state_string`, top-level `game_turn`, and `state` with `player_states`,
`car_states`, and another `game_turn`. Car tuples are
`[lane_y, head_x, direction, speed, length]`. There is one user message, no
conversation history or system message. Settings remain temperature 0.6,
sampling seed 0, num_predict 2048, num_ctx 4096, keep_alive 5m, stream false.
The model tag is `qwen3:4b-q4_K_M`.

Source findings:

- `U` increments observed y; `D` decrements it; both clamp at the edges.
  Internal position counts in the opposite direction (`y = 9 - env.pos`).
- The player moves first. Reaching y=9 ends immediately, before traffic moves.
  Otherwise cars update, then collisions are tested at internal column 4.
- Structured coordinates use twelfths of a column. Tail formulas in the prompt
  match the structured encoding, but that encoding interpolates slow cars'
  timer phases. Actual collisions use integer car cells. Fast cars jump and
  collision checking does not sweep intermediate cells. Wrapping happens on
  a later update when the car head was already outside columns 0–8.
  Thus constant-speed arithmetic and ordinary modulo wrapping are only an
  approximation; the original prompt does not explain these details.
- A nonterminal collision resets player AND traffic to the seeded initial
  arrangement while preserving elapsed turns and score. At turn 100 there is
  no traffic reset because the episode has ended.
- Score starts at 100 and decreases once per step, including collisions and
  the goal step. There is no separate collision penalty. A timeout also returns
  done, so success is specifically a terminal U transition from y=8.
- Terminal observations are empty; looking only at the final observation
  would miss success. Maximum position includes the goal transition.
- RealtimeGym does not advance itself during HTTP calls. The runner's main
  thread steps it while one worker performs inference. The waiting action is
  **S**, including after previous U/D actions. It is unchanged. Invalid or
  truncated responses also fall back to S, now explicitly labeled
  `invalid_fallback` rather than `model`. Parsed invalid actions are null and
  `fallback_action` is separately recorded. Accepted syntax is unchanged:
  exactly U/D/S after whitespace trimming and case normalization, with
  `done_reason == "stop"`; thinking text is never parsed.

## Existing logs

`model_freeway_20261006T085432285367Z.json` verifies the reported 48/48 valid
raw S responses, median latency 1.621950 s, maximum y=0, zero collisions, and
failure at 100 turns. These are not parser fallback actions. There are 52
logged ticks during requests. `model_freeway_20261006T085620327145Z.json`
(thinking on) contains two valid raw U responses, median 52.370165 s, maximum
y=1, one collision, and no success. One response arrives after termination;
raw validity must not be confused with applied actions.

`model_freeway_20261006T085405893501Z.json` is explicitly a delayed scripted
probe (0.1 s ticks, 0.5 s delay), not model progress. It has 20 U responses,
maximum y=2, 14 collisions, and no success. No new pilot uses that interval.

## Controlled comparisons

`diagnose_freeway.py` warms the model and tests four states reached by reset
and action prefixes `""`, `"U"`, `"UU"`, `"UUU"` on seed 0 (real seed 1000).
Each state is validated by cloning the actual environment and stepping all
three actions. These checks are diagnostics only; no transition lookup,
oracle, or scripted action is supplied to the live model runner.

| Prefix | Current y | Immediate U outcome | Immediate S outcome |
|---|---:|---|---|
| empty | 0 | y=1, safe | y=0, safe |
| U | 1 | y=2, safe | y=1, safe |
| UU | 2 | y=3, safe | y=2, safe |
| UUU | 3 | collision, y=0 | y=3, safe |

Only one factor changes between adjacent strategies:

1. Original prompt, full observation: establishes hesitation on useful states.
2. Progress prefix, full observation: explicitly says staying forever loses
   and encourages crossing while retaining S/D as traffic choices.
3. Same progress prefix, structured observation: removes only `state_string`.
   This separates shorter input from changed objective wording.

Complete requests, raw responses, parsed/fallback actions, timing,
observations, all validated transitions and selected outcomes are in
`logs/controlled_freeway.json`. Future diagnostic runs use timestamped names
to preserve all previous results. These immediate-action checks do not model
staleness during HTTP inference and do not count as model episode progress.

| Strategy | Raw actions in state order | Valid | Median response time | Dangerous state |
|---|---|---:|---:|---|
| Original + full | S S S S | 4/4 | 1.820 s | avoids collision by S |
| Progress + full | U S U U | 4/4 | 1.676 s | U collides |
| Progress + structured | U U U U | 4/4 | 0.998 s | U collides |

The shorter prompt and crossing instruction reduce hesitation. They do not
establish sound collision prediction: both variants fail the dangerous check.
These are single samples per state with a fixed sampling seed, not statistical
estimates of action probabilities.

## Reproduction

From the repository root, with Ollama already running:

```sh
.venv/bin/python -m unittest test_model_freeway.py
.venv/bin/python diagnose_freeway.py
.venv/bin/python run_model_freeway.py --prompt original --board full --thinking off --tick-seconds 1 --seed 0
.venv/bin/python run_model_freeway.py --prompt progress --board full --thinking off --tick-seconds 1 --seed 0
.venv/bin/python run_model_freeway.py --prompt progress --board structured --thinking off --tick-seconds 1 --seed 0
.venv/bin/python run_model_freeway.py --prompt progress --board structured --thinking on --tick-seconds 1 --seed 0
```

Run model commands sequentially to avoid inference contention. Each pilot
warms the model before the clock starts, logs that warm-up separately, and
writes a timestamped JSON file. Original prompt/full board remains the default;
select the progress variant explicitly. Existing sampling settings and the
waiting/fallback action S are unchanged. No tick interval adjustment was made.
Tests cover strict parsing (including truncated responses and thinking-only
content), independent board removal, and snapshot preservation. An additional
comparison against the initial Git version confirmed original prompt identity.
Python compilation and `git diff --check` passed.

New local metadata also records Ollama version 0.35.1 and model digest
`2bfd38a7daaf4b1037efe517ccb73d1a3bbd4822cf89f1a82be1569050a114e0` in
`logs/diagnosis_ollama_inventory.json`. No alternate model was needed or fetched.

## Live pilots and interpretation

The new pilots are actual asynchronous model episodes, all seed 0 and exactly
1.0 s configured ticks. Warm-ups are excluded from decision latency. Validity
counts include completed responses that arrive too late to apply; applied
counts are reported separately. All episodes run to environment termination.

| Configuration | Valid responses | Applied responses | Median latency | Max y | Collisions | Success |
|---|---:|---:|---:|---:|---:|---|
| Historical original/full, thinking off | 48/48 | 48 | 1.622 s | 0 | 0 | no |
| Historical original/full, thinking on | 2/2 | 1 | 52.370 s | 1 | 1 | no |
| Progress/full, thinking off | 50/50 | 50 | 1.638 s | 7 | 8 | no |
| Progress/structured, thinking off | 53/53 | 52 | 1.013 s | 5 | 13 | no |
| Progress/structured, thinking on | 0/2 | 0 (one fallback) | 81.798 s | 0 | 0 | no |

The progress/full pilot returned 26 U and 24 S actions. All 50 were applied;
there were another 50 waiting S steps. Six of eight collisions occurred on
waiting steps. Its full log is
`logs/model_freeway_20261008T021532150892Z.json`; console output is
`logs/pilot_progress_full_off.txt`.

The structured-only pilot returned 52 U and one late S. The S was discarded
after the episode; 52 model U actions were applied. Twelve of thirteen
collisions occurred while waiting. Its full log is
`logs/model_freeway_20261008T021721799409Z.json`; console output is
`logs/pilot_progress_structured_off.txt`.

Thus the full-observation progress prompt is the better observed configuration
for the requested objective. The shorter input improved latency but made the
model nearly indiscriminate about U and did not improve crossing progress.
Neither change is a collision-avoidance solution. No alternate model or
larger download was needed because actual pilots already demonstrate valid
model actions and substantial upward progress.

`logs/pilot_audit.json` checks applied model actions against their parsed
responses and confirms waiting actions remain S. The full and structured
thinking-off pilots respectively have 50 and 48 ticks occurring inside
request intervals. Their median actual tick intervals are both about 1.002 s;
maximum intervals are 1.014 and 1.039 s. This is direct evidence that inference
does not pause traffic.

## Remaining limitations and changed files

This is a small pilot study on one seed, not a benchmark improvement claim.
Warm-up, OS scheduling and prompt caching can change latency. Historical
baselines were not explicitly warmed; the new controlled comparisons were.
The fixed sampling seed does not make asynchronous trajectories deterministic.
The prompt still simplifies integer-cell collision mechanics and boundary
updates; that wording was preserved to isolate the objective and board
experiments. Thinking time can make observations extremely stale. There is
no prediction of the future action-application time, no action shielding,
and no forced upward action. Reaching y=7 is progress, not a completed crossing.

Changed/new source and documentation files:

- `run_model_freeway.py`: selectable progress prompt and independent board
  removal, preserved original default, pre-episode warm-up, shared strict
  parser/request builder, explicit fallback logging, maximum-position summary.
- `diagnose_freeway.py`: reproducible reachable-state comparisons, warm-up,
  environment transition validation, complete timestamped diagnostic logs.
- `test_model_freeway.py`: strict response boundary and prompt isolation checks.
- `docs/freeway_diagnosis.md`: this audit, evidence, outcomes and reproduction.

New evidence files are under the existing ignored `logs/` directory, including
failed experiments. They remain local and are not versioned. The existing logs
were preserved. No commits, pushes, PRs or GitHub modifications were made.

The thinking-on pilot uses the same structured progress prompt, sampling
settings, and 2048-token generation limit. Its first response used all 2048
output tokens, ended with `done_reason="length"`, and had empty final content
(7042 characters of thinking). At 81.591 s it was rejected, with parsed action
null and explicit S fallback. This is not a valid model S response. The live
episode timed out at y=0 with zero collisions. The outstanding second response
is collected after termination solely to complete the evidence; it cannot act
on the game. Full log:
`logs/model_freeway_20261008T021911649644Z.json`, console:
`logs/pilot_progress_structured_on.txt`.

Both thinking-on responses ultimately exhausted the 2048-token budget with empty final content. The second was discarded after termination. There were 99 ticks during requests, 99 waiting S steps, and one invalid-response S fallback. No valid model actions were applied. No further trials were run after this comparison.
