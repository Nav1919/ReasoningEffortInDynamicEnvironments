# Implementation steps

Working breakdown of `spec.md`. Do not treat a step as done until it is reviewed. Stop after each numbered step.

**Hypothesis:** An actor chooses better Freeway actions when it sees observer reasoning, the current observation, both, or neither, under a token reveal budget rather than wall-clock delay.

**Dependencies:** local Ollama, frozen `qwen3:4b-q4_K_M`, RealtimeGym Freeway, existing `run_model_freeway.py` prompt/parse/log shape.

**Locked defaults:** live observation during the `reasoning` / `both` inner loop; fallback action `S`; observer thinking on; actor thinking off; temperature `0.6` and seed `0`.

**Compute:** no live model episodes until Step 6. Offline tests must not call Ollama.

**Out of scope:** wall-clock ticks, a Freeway adapter class, duration-matched `observation`, swapping models, routing `x` / `time_pressure`.

The model client does **not** know `context_mode`, `x`, or `time_pressure`. The runner owns those.

---

## Step 1. Shared model client (`models.py`) — done

1. `call_reasoning_model` wraps local Ollama `/api/chat`. Default model is `qwen3:4b-q4_K_M`.
2. `call_decision_model` exists and raises `NotImplementedError`.
3. `parse_action` accepts only a completed `U` / `D` / `S`.
4. `ModelConfig` holds connection/sampling settings only (no experiment mode).
5. Failed requests are returned in `GenerationResult`, not dropped.
6. Offline tests: `python -m unittest tests.test_decision_models -v`.

**Not in this file:** token chunking, reveal schedule, `context_mode`. Those belong in the runner.

---

## Step 2. Observer (`observer_agent.py`)

1. Take a `ModelClient`. `think(observation)` builds a Freeway prompt that asks for reasoning only (no action letter).
2. Call `call_reasoning_model` with `max_tokens=x` and thinking on.
3. Return the reasoning string. Keep the full `GenerationResult` so the runner can log tokens, latency, and failures.
4. Do not parse or execute `U` / `D` / `S`.
5. Offline test: stub the client; check the prompt contains the observation and does not ask for an action letter.

---

## Step 3. Decision-model call + actor (`models.py`, `actor_agent.py`)

1. Implement `call_decision_model` as the same Ollama chat path, defaulting to the same frozen Qwen tag, with thinking off.
2. `ActorAgent.act(context)` sends the runner-built context and asks for only `U`, `D`, or `S`.
3. Parse with `parse_action`. Invalid/truncated output is a failure plus fallback `S`.
4. The actor does not know `context_mode`.
5. Offline tests: stub the client; reject prose/truncated output; confirm fallback `S`.

---

## Step 4. Token reveal helpers (runner-owned)

1. Count tokens for an observer trace. If model tokenization is unavailable, use a named approximation and record it in the episode log. Do not silently switch methods.
2. `ceil(actual_token_count / time_pressure)` prefixes. Example: 10 tokens, pressure 3 → lengths 3, 6, 9, 10.
3. A short or empty trace does not invent extra steps.
4. Offline tests for the schedule only. No Ollama.

---

## Step 5. Actor context builder (runner-owned)

1. `observation`: current environment observation only.
2. `reasoning`: revealed reasoning prefix only.
3. `both`: revealed prefix plus **live** observation (the state after previous inner steps, not the frozen observer snapshot).
4. Offline tests that each mode includes/excludes the expected parts.

---

## Step 6. Episode runner loop (`experiment_runner.py`)

1. CLI: `--context-mode`, `--time-pressure`, `--observer-tokens` / `-x`, `--seed`, `--model`, `--model-seed`, `--thinking` (observer only), `--board {full,structured}`, `--log-path` (refuse overwrite).
2. `ExperimentRunner(observer, actor, args)`. Create Freeway with `realtimegym.make("Freeway-v0", seed=..., render=False)`. Do not inject an env object.
3. Fetch model metadata and run warmup **before** `env.reset()` / the first `think` or `act`.
4. `observation` mode: one `act` and one `env.step` per state. Never call `observer.think`. Ignore `x` and `time_pressure` (log them as unused).
5. `reasoning` / `both`: observer thinks once; reveal `time_pressure` tokens per step; actor acts once per step; stop if the episode ends mid-trace. No default `S` filler ticks.
6. Print per-turn progress. Copy episode-script shape from `run_model_freeway.py`, not the wall-clock scheduler.
7. Offline tests with stub observer/actor: observation never calls think; inner loop uses actual token count; episode end mid-trace does not call `act` again; RealtimeGym reset/step smoke.

---

## Step 7. JSON logging

1. One JSON file per episode. Write in `finally`, including failures and unused leftover reasoning.
2. Settings: model, seeds, `x`, `time_pressure`, `context_mode`, observation freshness (`live`), tokenization method, which of `x` / `time_pressure` were unused.
3. `observer_cycles[]`: empty in `observation`; otherwise snapshot, full reasoning, token counts, latency.
4. `steps[]`: turn, revealed-token count (`0` in `observation`), context mode, context, action, source (`actor` / `fallback`), score, collision, done.
5. `summary`: turns, collisions, final score, success (terminal `U` from player y=8), unused reasoning tokens, observer-call count (`0` in `observation`).
6. Offline test: stubbed episode writes the expected keys.

---

## Step 8. Live smoke (after Steps 2–7)

One short Ollama run per `context_mode` with tiny `x`. Confirm logs exist and match the mode. Do not treat outcomes as results.

**Stop condition:** all offline tests pass; three smoke logs exist; no held-out tuning; failed requests kept.
