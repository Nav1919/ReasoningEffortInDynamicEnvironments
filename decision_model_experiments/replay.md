# Debug a saved decision-model episode

Open a saved `experiment_runner` log with the same Freeway environment installed
for the runner. This is a native pygame dashboard; no web server or Ollama is
needed. From the checkout containing this feature, with the repository's virtual
environment activated:

```sh
python -m decision_model_experiments.replay /absolute/path/to/logs/both_test.json
```

Pass any saved decision-model episode (`observation`, `reasoning`, or `both`).
JSON and gzip JSON are supported. Historical `run_model_freeway.py` logs use a
different trace schema; use the root `replay_freeway.py` for those instead.
For an offline check with no window:

```sh
python -m decision_model_experiments.replay EPISODE.json --verify-only
```

The window starts paused at the **state before the first action**. The action,
prompt and reasoning always belong to the selected step. **After** changes the
board to the outcome of that same action. It does not advance the selected step.
At the final step, After shows the terminal board. Freeway resets the player's
position when a crossing ends, so its terminal board can show the player back at
the bottom; the overlay states the verified outcome.

- **Left/Right**, **Prev/Next**: move one saved action.
- **Home/End**, **|< / >|**: first/last action.
- **B**, **Before/After**: toggle the board phase for the selected action.
- **Space**, **Play/Pause**: autoplay; stops at the end. Play from the last step
  restarts at the first. The speed button cycles 0.5, 1, 2, and 4 steps/second.
  This is inspection speed, not a recreation of model latency or game timing.
- Click the timeline to seek. Orange marks identify collisions or fallback actions.
- **N**, **Next issue**: jump to the next collision, fallback, or actor error.
- Click a tab (or **Tab** to cycle). Wheel, **Up/Down**, and **PgUp/PgDn** scroll
  the text. **+/-** adjusts text size. Resize the window for more reading space.
- **Esc**, or close the window: exit.

The tabs display:

- **Actor prompt**: the exact prompt saved in `actor_result.prompt`, followed by
  the saved runner context. No prompt is rebuilt using today's agent code.
- **Reasoning**: the prefix revealed at this step, its unrevealed suffix, and the
  full saved observer trace. The first two are reconstructed using the log's
  named whitespace approximation and reveal count. The full trace retains its
  recorded paragraphs. Future/unknown tokenizers show a warning and the saved
  actor context remains available. Full/unrevealed text is debugger information,
  not additional information supplied to the actor during the experiment.
- **Observer prompt**: that step's observer cycle prompt and original observation,
  which may be older than the board currently displayed.
- **Outputs**: actor output, recorded thinking, errors, finish reasons, usage,
  and complete saved generation records for actor and observer. Empty or absent
  fields are not replaced with invented reasoning.
- **State**: JSON observations before/after the action and the observer snapshot.
- **Episode**: verification scope, settings/seeds, summary/error, every observer
  call (including calls with no subsequent action), model metadata and warmup.

Before opening, replay starts the recorded seed and checks the initial state,
every observation, action transition, score, collision, terminal flag, turn, and
summary outcome against the installed simulator. Damaged/mismatching game records
exit with an error; there is no silent unverified board. The GUI renders detached
raw simulator positions/timers using the live runner's sprite-free Freeway drawing.
It does not approximate car locations from the model's interpolated `car_states`.

A partial episode can verify its recorded prefix without being a completed game.
Its saved error remains visible. A setup failure with no initial observation
opens an inspector with no board and the status **No game state recorded**;
it is not marked verified. Empty observer traces and failed generations are
retained. Missing prompts say **Not recorded**. Verification concerns game
transitions, not the truth of model reasoning or the consistency of prompt text
and reveal metadata. No log is modified and no inference is repeated.

## Task contract and reproducibility

**Hypothesis:** A verified Freeway board paired with the exact saved model inputs,
outputs and reveal boundary makes individual decision failures inspectable. This
is a debugging-tool hypothesis, not a new agent-performance result.

**Dependencies:** existing pinned Freeway/pygame environment, runner JSON schema,
and `experiment_runner.draw_freeway_surface`. No new package, model, credential,
server, or scientific decision is required.

**Acceptance checks:** replay real saved logs in all three modes; reject corrupt
transitions and summaries; preserve exact prompts and failed requests; inspect
before/after states; test seeking, playback boundaries, scrolling, tabs and
resizing; visually inspect both default and minimum layouts.

**Artifacts:** `replay.py`, `replay_gui.py`, `tests/test_decision_replay.py`, this
guide, README navigation and the human-review handoff in
[`replay-handoff.md`](replay-handoff.md). Test model text is explicitly synthetic.
Original ignored research logs remain unchanged and are not republished.

**Seed/config manifest:** unit fixtures use requested seed 0, its simulator-mapped
real seed, all three context modes, and synthetic whitespace-reveal text. Tests
record actual Freeway transitions for U actions, including collisions/time limit.
Saved-log checks use each file's existing environment seed/model settings and
preserve its frozen model; see the handoff for the actual checked files.

**Compute allowance:** bounded local offline tests and replay only; zero LLM
requests, generated model tokens or paid API use. No new experiments or held-out
policy tuning. Stop when acceptance checks pass and a reviewable commit exists.
Human review and merge remain required.

## Tests

```sh
python -m unittest discover -s tests -p 'test_decision_replay.py' -v
python -m unittest discover -s tests -v
python -m unittest discover -v
```

GUI regression tests use SDL's dummy video/audio drivers. They exercise mouse and
keyboard events and render every tab; they do not prove native desktop behavior
on every operating system. See the handoff for actual commands/results, screenshots
used in layout inspection, and remaining uncertainty.
