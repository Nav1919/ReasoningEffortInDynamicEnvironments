# Fair reasoning-mode comparisons — Step 2

New comparisons will keep observations, user instructions, model artifact and
supported generation settings fixed. Only the explicit reasoning control changes.
Existing Qwen off/on is a boolean comparison; it is not native Low/Medium/High.
A generated-token ceiling is a shared limit, not an effort level.

Offline: `python reasoning_modes.py` lists both definition sets and
`python -m unittest test_reasoning_modes.py` checks them. The historical runner
still sends exactly the same Qwen requests. Definitions alone do not certify
that a selected model supports a control; capability checks follow separately.

This work is stacked above unmerged PR #9, preserving its evidence unchanged.

## Capability checks and model-selection blocker (October 19)

`python model_capabilities.py` lists explicit, evidence-backed profiles.
Qwen uses booleans; GPT-OSS uses low/medium/high. The installed server's
`thinking.values` takes precedence; without it the fallback is restricted to
Ollama 0.35.1 and the verified architecture family. Unknown profiles, levels,
family mismatches and unverified fallback versions fail locally.

Sources: [installed-release thinking documentation](https://github.com/ollama/ollama/blob/v0.35.1/docs/capabilities/thinking.mdx)
and [OpenAI Ollama guide](https://developers.openai.com/cookbook/articles/gpt-oss/run-locally-ollama).
The server documentation explicitly warns unsupported named values can default;
we reject them instead. Profile validation alone cannot verify installed weights.

Local audit: Ollama client/server 0.35.1, 16 GiB RAM, about 72 GiB free disk.
Only Qwen models are installed. [GPT-OSS 20B](https://ollama.com/library/gpt-oss:20b)
is listed at about 14 GB and a minimum of roughly 16 GB memory: local execution
is marginal until measured. No download, upgrade, API substitution or pilot calls
were performed. Native-model selection and the 18-request pilot remain blocked
on a resource decision. Offline implementation continues without pretending
Qwen off/on supplies native Low/Medium/High results.

## Explicit recipes

`python experiment_config.py configs/qwen_boolean.json --ready` validates the
existing-model recipe offline. `configs/native_effort_draft.json` is a separate
native design with a null expected digest; `--ready` rejects it until model
selection is resolved. No historical records are assigned these new recipes.
Both use one shared validator and will feed the existing request/study functions.
All effective scientific settings are explicit; unsupported options are rejected.

## Matching instructions

`build_comparison_request` extends the existing runner's request construction;
for a matching observation/interval its requests differ only in `think`.
Qwen changes false/true; native effort changes low/medium/high. Tests compare
entire requests, not just their labels. Provider-internal formatting may differ.
`prompt_record` saves the exact instruction prefix and SHA256 per condition.

The pinned simulator's step/state-builder source was inspected: player moves
before traffic, goal ends immediately, collisions check updated integer cells,
wrapping is delayed, and nonterminal collisions reset traffic. Existing
`progress_source` describes those mechanics correctly, but omitted edge clamps.
New `progress_source_v2` adds only that clarification. Original/progress and the
historical source-corrected template remain unchanged. Frozen diagnostics keep
these same user instructions; their asynchronous wording limits interpretation.

## Two configuration identifiers

`resolve_run` saves a detached full recipe, selected mode/start/interval/replicate,
and the exact instruction template. The comparison SHA256 covers **every recipe
field**, including the complete mode set, seed splits/order/replicates and each
interval's instruction fingerprint. The run-configuration SHA256 additionally
selects the mode. Canonical JSON makes dictionary order irrelevant; paths and
clock times are never inputs. A different token ceiling or mode set changes the
comparison ID. Same-comparison runs still need matching actual start, condition
and replicate before they can be paired. Reserved starts cannot be executed here.

## Check the installed model without generating text

`python model_provenance.py configs/qwen_boolean.json` reads local Ollama
version, inventory and model metadata. It requires the exact tag **and digest**,
checks the actual family/controls, and returns the template and capability evidence.
Mismatch, absence or unresolved digest stops setup. It never pulls a model.
All requests use the recipe timeout. Ollama tags are mutable; do not replace
weights during a run. Metadata validates setup, not action quality.

## What code and environment actually ran

`source_provenance` fingerprints relevant root-level runnable sources and records
the current commit/local-modification flag, Python/dependency versions, basic
machine details, and the installed Freeway source hash. It stops on a source
mismatch. RealtimeGym revision comes from package VCS metadata or its editable
checkout when recoverable; otherwise it is null with a reason. An installed
wheel is not assumed to contain Git history. Unavailable hardware data is also
explicitly null. Source hashes identify modified code even without a clean commit.

## Development and reserved starts

`python experiment_starts.py configs/qwen_boolean.json` verifies initial states
without playing reserved games. The saved mapping in `configs/freeway_starts.json`
is 0..7 → 1000,1001,1002,1003,1013,1014,1016,1018. Each has a distinct actual seed
and complete initial-state fingerprint, including hidden timers/RNG. Selectors
0..4 remain development. Local historical episode JSON used only 0..4; 5..7
are reserved evaluation starts, with just three available starts—a real limit.
Duplicate actual seeds **or** initial layouts are rejected across the entire split.
Environment selectors, model sampling seed and scheduling seed remain separate.

## Response records

A valid model `S` is distinct from a waiting step and invalid-response fallback S.
`decision_record` separately records request status, received/absent response,
action validity, action application, and measurement availability. For example,
`eval_count: 0` stays zero; an absent count becomes null with an explanation and
does not invalidate a good U/D/S answer. `eval_count` is output, not reasoning tokens.
Timeouts, request errors, malformed responses, invalid actions, truncations and
late/discarded responses remain explicit. Raw provider responses are preserved.

## Setup cannot disappear

`setup_run` exclusively creates a run file before any network/model setup.
It saves resolved settings, source/start checks and model metadata. If Ollama is
unavailable, the file says `setup_failed`, `model_setup`, and the actual error.
Interrupted setup is saved too. Reusing the same filename fails rather than
replacing evidence. Retry attempts must use new explicit attempt/run identifiers.

## Existing live runner, saved settings

`python run_model_freeway.py --experiment-config configs/qwen_live.json --mode off --seed 0 --tick-seconds 1`
uses the existing traffic/inference loop, but performs recorded setup first and
saves the resolved recipe, both IDs, source/model/start evidence and detailed
response records in the episode. On uses the same command with `--mode on`.
Recipe-controlled settings cannot be overridden with legacy model/prompt flags.
Historical commands and default prompts remain supported. Warm-up uses a supported
control outside gameplay timing. Offline tests use fake responses and clocks.

## Save a plan before model calls

`python freeway_study.py plan --config configs/native_effort_draft.json --output logs/native_plan_01 --dry-run`
saves an offline `plan.json`, even while model selection is unresolved. It contains
18 requests: two existing situations per category × three levels, one shared
2048-token ceiling and one interval. Selection takes the first two selectors per
category before a seeded shuffle; no model answers influence selection. Rotating
levels gives each level each order position twice. Full resolved settings,
rendered requests, actual starts, conditions and replicate/attempt IDs are saved.
Qwen's separate recipe makes its own plan. The design itself enters comparison
identity. Live plans cover development starts only; new retries require `--attempt 2`
and a new output directory. Existing plans cannot be overwritten.

`configs/qwen_live.json` is the separate live-game recipe. The runner rejects
a frozen-pilot recipe for live gameplay so the saved design cannot be mislabeled.

## One frozen pilot request

`run_frozen` uses the existing model-call and parsing helpers after recorded
setup and a separately logged warm-up. Traffic is frozen for the measured call;
its returned action is checked on an independent simulator copy, not executed in
a live game. It saves latency, raw answer, token availability, immediate safety
and the category's relevant choice. Waiting-useful means a first action compatible
with the saved short safe-progress sequence, not proof the model completes it.
Invalid answers remain invalid; there is no executed fallback in this diagnostic.

## Execute only the saved plan

`python freeway_study.py execute --output logs/native_plan_01 --limit 1`
checks the saved plan before making calls, creates an execution manifest, and
attempts at most one run. Frozen runs use the existing helpers; live runs invoke
the existing runner with the saved recipe. Every future/unrun entry stays
`planned`. Setup failures and timeouts stop further requests. A client timeout
does not prove server computation stopped: verify Ollama is idle before retrying.
Existing execution files are rejected; create a new plan/folder with a new attempt
ID to retry. `--limit 18` is the explicit full native pilot, currently blocked.

## Pairing and missing partners

New summaries check the saved plan/config IDs, actual model/environment identities
and runnable source fingerprints. Pairing uses comparison ID + actual initial
start + situation observation + interval + replicate + attempt, never the selector
alone. Each mode keeps its status; an unrun/failed partner is named explicitly.
A folder of historical Qwen records cannot be pooled into this comparison.
