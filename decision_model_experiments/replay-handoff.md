# Decision-model replay: human-review handoff

Implemented November 26, 2026 with Codex assistance. Human review is pending.
Feature commit: `237db584e400254e4f04086e1d6e14df50c24f1d` on
`codex/decision-trace-replay`, based on `3065ad8`.
The subsequent documentation commit contains this handoff; use `git log -2` for
its SHA. Nothing was pushed, merged, self-approved or security-configured.

The repository's configured author, `AkashWudali12 <akash.wudali@gmail.com>`,
was checked against recent commit authors and used unchanged. The commit message
explicitly discloses agent implementation/validation. Author attribution does
not assert a particular authenticator, pusher or signing identity.

## Scope and artifacts

The [task contract](replay.md#task-contract-and-reproducibility) states the debugging
hypothesis, dependencies, acceptance checks, seed/config manifest, offline compute
allowance and stop condition. This work makes saved decision traces inspectable;
it supplies no new policy-performance evidence and changes no frozen model,
prompt, reveal policy, experimental action or existing log.

Changed paths:

- `decision_model_experiments/replay.py`: read-only JSON/gzip loading, game
  verification and readable saved-text panels.
- `decision_model_experiments/replay_gui.py`: existing Freeway rendering alongside
  before/after navigation, timeline, playback, tabs, scrolling and font controls.
- `decision_model_experiments/experiment_runner.py`: optional terminal label in
  `draw_freeway_surface`, so replay can label a verified win even on turn 100;
  original callers retain their behavior.
- `tests/test_decision_replay.py`: 19 offline evidence/navigation/GUI tests.
- `decision_model_experiments/replay.md`, this handoff, `README.md`, and
  `docs/testing.md`: launch instructions, controls, verification scope and tests.

The isolated worktree is `/private/tmp/decision-trace-replay`. The original checkout
remains on `akash/token-based-time`. Its pre-existing edits to `observer_agent.py`
and `tests/test_observer_agent.py` were not copied, altered or included.

## Actual validation

Commands below ran from the isolated worktree unless otherwise stated. `PY` below
means the existing interpreter
`/Users/akashwudali/ReasoningEffortInDynamicEnvironments/.venv/bin/python`.
This is a documentation shorthand, not a shell environment variable.

- `PY -m unittest discover -s tests -p 'test_decision_replay.py' -v`:
  first 17 tests passed; after the final pause-at-end regression and event-loop
  exit test, **19 tests passed** (0.638 seconds). Final execution used
  `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy`.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PY -m unittest discover -s tests -p 'test_experiment_runner.py' -v`:
  **36 passed** (0.127 seconds), including the real simulator and existing renderer.
- `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PY -m unittest discover -v`:
  **14 passed** (4.404 seconds), including published-file checksums, all 15 historical
  episode replays and relocated summary regeneration.
- `PY -m unittest discover -s tests -v` before the final two new tests:
  **81 of 82 passed; one failed**, in
  `test_freeway_smoke.RealEnvironmentTests.test_independent_cli_repeatability_and_record_oracles`.
  Its exact-record comparison includes dependency provenance: the saved smoke
  sample uses NumPy 2.2.6/Python 3.13.5; the installed interpreter has
  NumPy 2.5.3/Python 3.13.12. Both use pygame 2.6.1/RealtimeGym 0.1.0.
- `PY -m unittest discover -s tests -p 'test_freeway_smoke.py' -v` from the
  **original checkout**: **6 of 7 passed; the same provenance comparison failed**.
  This confirms the failure exists without the replay changes. Its saved evidence
  and dependency installation were left intact. A matching historical environment
  was not installed or tested as part of this task.
- `git diff --check`: passed before commit.
- Initial `git worktree add` failed because sandbox permissions prevented creation
  of the branch ref; the approved retry created the isolated worktree successfully.
  No research runs were lost or marked successful because of this tooling failure.

The initial broad test run emitted macOS application-notification messages when an
existing renderer test initialized pygame without the dummy driver. That renderer
test passed; subsequent explicit renderer checks used dummy SDL.

## Existing episode checks

`PY -m decision_model_experiments.replay /absolute/path/to/logs/both_test.json --verify-only`
passed: 100 verified steps and 20 collisions.
A separate Python invocation used `load_trace` on all three logs below, hashing
bytes before and after to assert no modification. All use requested seed 0,
mapped seed 1000, `qwen3:4b-q4_K_M`, model seed 0 and observer budget 256.

- `both_test.json`: mode both, pressure 32, observer thinking on;
  **100 transitions / 20 collisions verified**;
  SHA256 `48a9af60032d4c270e8b484c299adf73d789c23e3b0a83cb1fd61c5d2a629df4`.
- `observation_test.json`: mode observation, pressure 8 and observer thinking on
  are unused by that mode; **100 transitions / 25 collisions verified**;
  SHA256 `2316a20dd4f79849e7a6ba73333f9817b2d61fd7e4bfd87403b8a5f34bbefe8f`.
- `reasoning_gui2.json`: mode reasoning, pressure 32, observer thinking on;
  **46 transitions / 6 collisions verified**;
  SHA256 `e282d31b32537301edfaee17293627a079f1408d4cef1dfa167e8fa4d5dae53f`.

All three saved episode errors are null. These are checks of existing records,
not newly executed model experiments. The source files remain in the original
checkout's ignored `logs/` directory; they were not republished in Git.

## Layout and interaction checks

Using dummy SDL, loaded `reasoning_gui2.json`, selected step 13, drew the Reasoning
and Actor prompt tabs, and visually inspected screenshots at 1400x900 and 1140x760.
The minimum-size inspection revealed a footer overlap; adjusted the board sizing,
rendered again and verified the corrected screenshot. Temporary QA files:
`/private/tmp/decision-trace-replay-layout.png` and
`/private/tmp/decision-trace-replay-small.png`. These are local inspection artifacts,
not committed research data. Tests exercised tabs, scrolling, font wrapping,
mouse timeline/tab clicks, keyboard navigation, resizing, before/after selection,
play/pause at the last step, failure-only logs, and clean event-loop exit.

## Usage, cost and uncertainty

Local offline simulator replay and tests only; **zero experiment LLM calls,
zero generated experiment-model tokens, zero paid experiment API use**. Agent
service token/cost accounting is not available and is not estimated here.
No live smoke episodes, model downloads, held-out tuning or fresh installations
were performed. The full `tests/` suite was not rerun after the final two focused
GUI tests; the affected replay suite and shared runner suite passed afterward.

Desktop interaction was verified with SDL input events and rendered screenshots,
not a manual native-window session. Native behavior on other operating systems
remains unverified. Very long prompts require scrolling. Replay requires compatible
Freeway behavior and exits on a mismatch. The verification checks game transitions,
not inference reproducibility or semantic consistency of saved prompt/reveal text.
Missing model reasoning is never invented. Historical non-decision-model logs
remain supported through the separate root replay tool.

Please review the isolated branch and try a native-window replay before merging.
