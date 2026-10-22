# No-LLM Freeway smoke check

This is source/API and short-run repeatability verification, **not** a reasoning-effort evaluation or scientific result. No inference client or model is selected. Implementation and documentation were prepared with Hermes/Codex assistance, for human review.

## Pinned minimal runtime

Upstream: [SALT-NLP/RealtimeGym](https://github.com/SALT-NLP/RealtimeGym/tree/3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b), revision `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b` (MIT). The tested runtime is an external **unmodified selected-source Freeway path**, not a full upstream package installation. Nothing upstream is vendored here. Its external source manifest includes selected-file and wheel SHA-256 values, also recorded as provenance in [the run manifest](../artifacts/freeway/manifest.json).

Tested: Linux x86_64, CPython 3.13.5, NumPy 2.2.6, pygame 2.6.1. [requirements-freeway.txt](../requirements-freeway.txt) pins only the two packages needed for this headless import path. The renderer module imports pygame even with `render=False`. Full upstream installation has additional dependencies; this does not verify those dependencies or other environments. No network access or package installation was performed for this task.

The provisioned paths below are specific to the verification machine. For another machine, obtain the pinned upstream source separately and supply its `src` directory and your compatible dependency directory through `PYTHONPATH`. Installing these pins into a separate Python 3.13 environment is an **untested setup suggestion**, not an installation validated here. The runner itself contains no machine-specific paths and checks hashes of the four imported implementation files against the supplied source manifest before running.

## Tested commands (from repository root)

```sh
export PYTHONPATH=/opt/data/research/freeway/source/src:/opt/data/research/freeway/site-packages
export PYGAME_HIDE_SUPPORT_PROMPT=1
export SDL_VIDEODRIVER=dummy

# This exact command created the committed sample; output must not already exist.
/usr/bin/python3.13 scripts/freeway_smoke.py --output artifacts/freeway/smoke-seed0.jsonl

# Seven tests, including a second independent real-environment CLI process.
/usr/bin/python3.13 -m unittest discover -s tests -v

# Supplied example, run unchanged as a third ten-step smoke run.
/usr/bin/python3.13 /opt/data/research/freeway/source/examples/basic_usage.py
```

To make a new log, use a new output filename rather than overwriting evidence:

```sh
/usr/bin/python3.13 scripts/freeway_smoke.py --environment Freeway-v0 --difficulty E \
  --seed 0 --actions USUSUSUSUS --max-steps 10 --output smoke-repeat.jsonl
```

The latter explicit-argument command is equivalent to the tested defaults, not an additional recorded run. Run `scripts/freeway_smoke.py --help` with the same interpreter for options. Parent output directories must exist. Errors are not turned into successful records; preserve failed command output separately if a run fails. The CLI opens output exclusively and never replaces an existing log. It collects at most 100 steps in memory before writing; it is not a streaming recovery logger.

## API and record semantics

The actual source, not the inconsistent upstream README snippets, defines:

- `realtimegym.make(env_id, seed, render=False) -> (env, actual_seed, renderer)`.
- `env.reset() -> (observation, done)`.
- `env.step(action) -> (observation, done, cumulative_reward, collision_reset)`.

`Freeway-v0/v1/v2` map to difficulty `E/M/H`. Input seeds are integers 0–7, not arbitrary RNG seeds; the returned mapped seed is recorded separately (v0 input 0 maps to 1000). The CLI requires the difficulty to match the environment. Actions are a finite, nonempty uppercase string containing only `U`, `D`, `S`; they are consumed once, not cycled. `U` moves up, `D` down, `S` stays. The runner stops at terminal done, action exhaustion, or the requested step limit (1–100). The upstream game has a 100-turn cap; no wall-clock deadline or pressure manipulation is applied.

Reward starts at 100 and decreases by one each turn: returned rewards are cumulative game scores, **not per-step rewards to sum**. A collision resets traffic/player internally while retaining reward and turn; `reset=True` is not terminal and must not cause an extra caller reset. Winning or the turn cap sets `done=True`; terminal observations are `{}`. The short actual sample exercises collision at step 8 but not terminal behavior. Synthetic tests cover terminal tuple ordering and stopping.

JSONL schema version 1 has one metadata record, one reset record, one record for each executed step, and one summary. Metadata includes revision, implementation hashes, dependency/interpreter versions, environment/difficulty, input/mapped seeds, requested actions and limits. Reset preserves its observation and done flag. Steps preserve full raw before/after observation values, action, ordinal, cumulative reward, done and collision-reset flags. Upstream observation tuples become JSON arrays without dropping fields. Summary records actual step count, last cumulative reward, done and stop reason. No timing values are included in these deterministic records; test duration belongs only to the manifest.

## Verification and limits

[Sample](../artifacts/freeway/smoke-seed0.jsonl): 13 records (metadata, reset, ten steps, summary); actions `USUSUSUSUS`; input seed 0 / mapped seed 1000; final cumulative reward 90; done false. Two independent processes at these identical settings produced exactly equal parsed records, including all raw observations, versions and source hashes. The upstream example independently produced ten steps and the same final seed/reward/done result. No failed runs occurred.

[Tests](../tests/test_freeway_smoke.py) reject invalid settings, bad mapped seeds and altered source hashes; check action exhaustion, snapshot preservation, collision-versus-terminal semantics and cumulative reward; and compare the actual subprocess replay with the sample. Independent record oracles and deliberate record mutations detect seed, action, observation-chain, reward and step-number errors. Integration requires this exact runtime (including Python patch version) because versions are part of equality; it fails rather than silently skipping missing dependencies/sample. Do not update a golden sample merely to silence a failure.

Not validated: all seeds or difficulties, full episodes/real terminal trajectories, rendering, other operating systems/interpreters, full upstream installation, wall-clock or token pressure, delayed observations, volatile real-time behavior, model quality, costs, or scientific generalization. Supported-setting unit checks are not evidence that every supported setting was executed. A teammate has not independently followed setup yet. Weekly tracker checkboxes remain unchanged.

Budget used: one coding worker; two real runner executions plus one unchanged example (each ten steps), unit checks, no inference/API calls and no paid experiments. Coding-assistant subscription usage is unmeasured; no dollar/token estimate is asserted.
