# Freeway situation bank

The bank saves reachable game situations and checks possible moves by running
copies of the simulator. It makes no model calls or manual board edits.

## Run it

Use the existing project environment and a new output directory:

```sh
.venv/bin/python situation_bank.py balanced --count 500 --ticks 89 --output data/situation_bank/freeway_bank_v2
.venv/bin/python -m unittest discover -v
```

The first command collects, labels, and verifies the bank. To verify it again:

```sh
.venv/bin/python situation_bank.py verify --output data/situation_bank/freeway_bank_v2
```

For a small random-policy pilot, run `collect`, `label`, then `verify` with the
same `--output` path. Collection defaults to 50 states.

## Collection

The 500-state run explores U, D, and S from five development starts, stopping
at collisions and game endings. It keeps the earliest visit to each distinct
player/traffic configuration, including movement timers. Each saved state has
both a full snapshot and a seed/action prefix for independent replay.

Selection favors underrepresented categories, then lanes and starting states.
If a category runs out, its remaining slots go to the others. Starts are limited
to selectors 0–4. The simulator accepts eight easy-mode selectors; an early failed
pilot also stepped 5–7, so those starts cannot be claimed as untouched test data.

## Answer keys

For each first action and horizon of 1–10 ticks, search checks whether any
continuation survives without a collision or reaches the goal. Collision resets
do not rescue a failed path; timeouts do not count as survival.

Prefer reaching the goal, then faster arrival. If no path reaches the goal,
prefer greatest final progress among surviving paths. Keep every tied first
action and one example sequence for each. These are bounded answers, not proof
of a best full-game strategy or safety under arbitrary later actions.

Categories are assigned in this order:

- **Must retreat:** only D has a safe continuation through the chosen horizon.
- **Waiting helps:** U collides now, but 1–3 stays followed by U makes safe progress.
- **Safe advance:** U advances safely and has a safe continuation.
- **Dangerous advance:** U collides and an alternative survives; earlier cases excluded.
- **Other:** none of the above; excluded from the 500-state selection.

A short waiting maneuver alone does not guarantee survival for all ten ticks.

## Results and files

The run found 2,938 candidates and selected 500. Every player position 0–8 has
55–56 states; each starting configuration contributes 100. See the
[run summary and examples](../data/situation_bank/freeway_bank_v2/README.md).

Git contains only the settings, checksums, small examples, and verification
summary. Full `states.json`, `labels.json`, and `candidate_inventory.json` stay
local and are ignored by Git. Regenerate them with the command above. The
manifest records the original generator source hash; later comment edits do not
change the generated states or answers.

Verification reconstructs every snapshot from its action prefix, recomputes
answers, and replays every saved solution. Tests also compare short searches
with all possible action sequences. `search_states` counts new cache entries;
it is a performance statistic, not an answer-key label.

## Research scope

Hypothesis: searching reachable states improves coverage over random collection.
Dependencies: the installed pinned simulator, NumPy, and the project environment.
Acceptance: 500 distinct states, every player position covered, and successful
replay and label checks. Compute: local CPU only, no GPU jobs or paid APIs.
Stop after collection and verification; no model experiments are included.

These are correlated development checkpoints from five starts, not 500 independent
games. Held-out splits, equivalent state renderers, and explicit forecasting
questions still need to be designed. Human review is required; implementation
and verification were AI-assisted.
