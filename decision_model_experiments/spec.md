# Decision-model experiment spec

This is an implementation plan only. Do not treat it as executed work.

## Goal

Test how well an actor (decision model) chooses actions when its context contains:

1. Observer reasoning only
2. Current environment observation only
3. Both

`reasoning` and `both` stream observer text into the actor while the environment steps. Time pressure is a token budget per step, not wall-clock latency.

`observation` is a reactive baseline: no observer, no reveal loop, one action per current state.

These modes are **not** duration-matched. Do not treat `time_pressure` as meaningful in `observation`.

## Layout

Keep the remaining scaffolding. Do not add `freeway.py` or `experiment.py` back.

| File | Role |
|---|---|
| `observer_agent.py` | `ObserverAgent.think(observation) -> str`. Generate a full reasoning trace from one observation. Unused in `observation` mode. |
| `actor_agent.py` | `ActorAgent.act(context) -> action`. Choose `U` / `D` / `S` from a built context string. |
| `models.py` | Shared LLM client, token counting, action parsing. |
| `experiment_runner.py` | Full episode entrypoint, modeled on `run_model_freeway.py`. Owns CLI, RealtimeGym env, the mode-specific loop, and JSON logging. |

`ExperimentRunner` no longer takes an injected environment object. It creates Freeway itself with `realtimegym.make`, the same way `run_model_freeway.py` does.

## What to copy from `run_model_freeway.py`

Copy the episode-script shape, not the wall-clock scheduler.

Copy into `experiment_runner.py`:

- module docstring, argparse, `if __name__ == "__main__"`
- `realtimegym.make("Freeway-v0", seed=..., render=False)`, `env.reset()`, `env.step(action)`
- refuse-overwrite `--log-path`, timestamped `logs/*.json`
- episode record with `settings`, `model_metadata`, `warmup`, `decisions` / observer cycles, `steps`, `summary`
- success rule: terminal `U` from player y=8
- `convert_scalar` for JSON
- warmup request before the episode clock/loop starts
- print per-turn progress

Move to `models.py` so both agents can share them:

- Ollama `post_json`
- `parse_action` (complete `U`/`D`/`S` only)
- request payload construction (`model`, `think`, `seed`, `num_predict`, `num_ctx`)

Do **not** copy:

- `ThreadPoolExecutor` / pending-request overlap
- waiting-default `S` ticks while a request is in flight
- applying a stale action on a later wall-clock tick

This experiment is discrete: the actor acts once per environment step. The observer is called only in `reasoning` and `both`.

## Frozen loop

`ExperimentRunner.run()` owns this loop end to end. Branch on `context_mode`.

```
env, real_seed, _ = realtimegym.make("Freeway-v0", seed=args.seed, render=False)
observation, done = env.reset()
while not done:
    if mode == "observation":
        context = build_actor_context("observation", revealed="", observation=observation)
        action = actor.act(context)
        observation, done, score, collided = env.step(action)
        continue

    reasoning = observer.think(observation)          # generate x tokens once
    n_chunks = ceil(len(reasoning_tokens) / time_pressure)
    revealed = ""
    for i in range(n_chunks):
        revealed += next time_pressure tokens of reasoning
        context = build_actor_context(mode, revealed, observation)
        action = actor.act(context)
        observation, done, score, collided = env.step(action)
        if done:
            break
```

Definitions:

- `x`: observer generation budget (`num_predict` / max reasoning tokens). Used only in `reasoning` and `both`.
- `time_pressure`: how many **new** reasoning tokens are appended to the actor context each environment step. Used only in `reasoning` and `both`.
- Inner-loop length (`reasoning` / `both` only): `ceil(actual_token_count / time_pressure)`. Use the actual trace length so a short/empty observer reply does not invent extra steps.
- In `reasoning` / `both`, the observer does **not** think again until the current trace has been fully revealed (or the episode ends).
- In `observation`, skip `observer.think` entirely. One `act()` and one `env.step()` per current state, then read the next observation.
- The actor acts once per environment step. No default `S` filler steps.

`time_pressure` and `x` are ignored in `observation`. Log them as unused if the CLI still accepts them; do not invent a reveal schedule from them.

## Actor context modes

`ActorAgent.act` stays a single method. The runner builds `context`; the actor does not need to know the experimental condition.

| `context_mode` | Actor sees | Loop |
|---|---|---|
| `reasoning` | Revealed reasoning prefix only | Observer once, then `ceil(tokens / time_pressure)` act/step cycles |
| `observation` | Current environment observation only | No observer; one act/step, then the next observation |
| `both` | Revealed reasoning prefix plus environment observation | Same reveal loop as `reasoning` |

**Lock before coding:** during the `reasoning` / `both` inner loop, is `observation` the frozen snapshot the observer saw, or the live state after previous inner steps? Recommended default: **live state**. That makes the revealed reasoning stale-by-construction and `both` able to notice that the world moved. This question does not apply to `observation`, which always uses the current state and then re-observes after one step.

## Implementation steps

### 1. Shared model client (`models.py`)

Implement a small client used by observer, actor, and the runner:

- `generate(prompt, max_tokens, think=...)` wrapping local Ollama
- tokenize/count helpers so chunking uses model tokens, not characters
- `parse_action` copied from `run_model_freeway.py`
- config fields the runner will pass through: model name, seed, temperature, `num_ctx`, observer `x`, `time_pressure`, `context_mode`

If exact tokenization is unavailable, record the approximation used in the episode log. Do not silently switch methods across runs.

### 2. Observer (`observer_agent.py`)

Fill in `think(observation)`:

- Prompt: describe Freeway, show the observation, ask for reasoning **only** (no action letter)
- Cap generation at `x` tokens
- Return the reasoning string; the runner records token count, latency, and the full trace

The observer is not the decision model. It must not emit `U`/`D`/`S` as the thing the environment executes. The runner must not call `think()` in `observation` mode.

### 3. Actor (`actor_agent.py`)

Fill in `act(context)`:

- Prompt: play Freeway, return only `U`, `D`, or `S`
- `context` is already the condition-specific string
- Parse strictly; invalid/truncated output is a logged failure plus a configured fallback (recommend `S`)
- Keep `think` off for the actor unless a later experiment explicitly asks for actor-side reasoning

### 4. Full episode runner (`experiment_runner.py`)

Make this file the analogue of `run_model_freeway.py`.

**CLI** (same style as the existing runner, plus the new factors):

- `--context-mode {reasoning,observation,both}`
- `--time-pressure` (tokens per step; ignored in `observation`)
- `--observer-tokens` / `-x` (ignored in `observation`)
- `--seed`, `--model`, `--model-seed`
- `--thinking` for the observer only (unused in `observation`)
- `--board {full,structured}` if the Freeway observation prompt is reused
- `--log-path` (refuse overwrite)

**`ExperimentRunner`:**

```
class ExperimentRunner:
    def __init__(self, observer, actor, args):
        ...

    def run(self):
        ...
```

`run()` should:

1. Call `realtimegym.make("Freeway-v0", seed=args.seed, render=False)`
2. Fetch model metadata and run warmup before `env.reset()` / the first `think` or `act`
3. Open the episode log dict
4. Execute the mode-specific frozen loop above
5. Build actor context from `context_mode` each act
6. Log every observer cycle (none in `observation`) and every env step
7. Write JSON in `finally`, including failures and unused leftover reasoning
8. Call `env.summary()` at the end

`main()` parses args, constructs `ObserverAgent` and `ActorAgent`, constructs `ExperimentRunner`, and calls `run()`. In `observation` mode the observer object may still be constructed, but `run()` must not call it.

Keep Freeway prompt wording in the runner (copied from `build_prompt`) or in the agent prompts; do not hide it behind a separate env adapter class.

### 5. Logging

One JSON file per episode, same spirit as `run_model_freeway.py`:

- settings: model, seeds, `x`, `time_pressure`, `context_mode`, observation freshness policy, which of `x` / `time_pressure` were unused
- `observer_cycles[]`: empty in `observation`; otherwise observation snapshot, full reasoning, token counts, latency
- `steps[]`: turn, revealed-token count (`0` in `observation`), context mode, context (or a hash plus the context), action, source (`actor` / `fallback`), score, collision, done
- `summary`: turns, collisions, final score, success (U from y=8), unused reasoning tokens, observer-call count (`0` in `observation`)

Preserve failed requests and invalid actions. Do not drop them.

### 6. Tests before any model episode

Add focused unit tests (no Ollama required):

- Chunking (`reasoning` / `both`): `x=10`, `time_pressure=3` → 4 steps, prefixes of length 3, 6, 9, 10
- `observation`: exactly one `act` and one `step` per state; `observer.think` is never called
- `context_mode` includes/excludes the expected parts
- Inner loop uses actual token count when the trace is shorter than `x`
- Episode end mid-trace does not call `act` again
- `parse_action` still rejects prose / truncated output
- Runner reset/step smoke against RealtimeGym with a stub observer/actor

Then one short live smoke run per `context_mode` with tiny `x` to verify logs.

## Recommended defaults to lock

These are suggested defaults, not results:

- Same frozen local model for observer and actor (`qwen3:4b-q4_K_M` unless changed)
- Live observation during the `reasoning` / `both` inner loop
- Fallback action `S` on invalid actor output
- Observer `think` on when the observer is used; actor `think` off
- Temperature / seed copied from `run_model_freeway.py` so later comparisons stay possible

## Out of scope for the first implementation

- Wall-clock real-time ticks
- A separate Freeway adapter or experiment entry module
- A duration-matched `observation` variant that still runs the reveal loop with unused reasoning
- Training or swapping models mid-study
- Router that chooses `x` or `time_pressure` from state
- New environments beyond Freeway
- Tuning on held-out seeds
