# Compare thinking settings

We want to know whether more thinking helps the AI choose a good move. Give each
setting the same game situation. Save the questions first. Then save every answer,
timeout, and question that never ran. Qwen thinking off/on is a separate comparison
from a model with low/medium/high settings.

## Try it without a model

After the README installation, run these commands from the repository root:

```sh
python experiment_config.py configs/qwen_boolean.json --ready
python freeway_study.py plan --config configs/native_effort_draft.json --output logs/native_plan_01 --dry-run
python freeway_study.py summarize --output logs/native_plan_01
python -m unittest discover -v
```

The plan has six situations, each asked at three thinking levels: 18 questions.
The summary says zero questions were attempted. All answers are still missing.
Use a new output folder each time. Existing records cannot be overwritten.
The draft leaves the model version undecided, so it cannot make real requests.

## Run one question with the installed Qwen model

Ollama must be running and the exact model from the README must be installed.

```sh
python model_provenance.py configs/qwen_boolean.json
python freeway_study.py plan --config configs/qwen_boolean.json --output logs/qwen_check_01
python freeway_study.py execute --output logs/qwen_check_01 --limit 1
python freeway_study.py summarize --output logs/qwen_check_01
```

This asks one measured question and a separate warm-up question. Look in `runs/`
for the request and answer. `execution.json` lists everything that did not run.
`comparison_modes.csv` shows the counts. A missing measurement stays missing;
zero is used only when the model actually reported zero.

## A saved picture and a live game are different

The default comparison holds the game still while asking a question. It checks
the answer in a separate copy of the game. This does not show whether the model
can cross the road while cars keep moving. For a live game, use the separate
`configs/qwen_live.json` recipe with the same plan and execute commands.

A timeout stops further questions. Check that Ollama is idle before retrying.
Use a new folder and `--attempt 2` when making a new plan for a retry.
Loading time can have a separate limit from the time allowed to answer.
No paid API calls or model downloads are part of these commands.

## Review order

1. `freeway-replay`: run the game and check the old saved experiments.
2. `fair-model-comparisons`: check settings, model versions, and game starts.
3. `saved-comparison-runs`: save a plan, run it, and explain every outcome.

Each change builds on the previous one. Review and merge them in that order.
The [testing guide](testing.md) lists the checks. The
[technical comparison notes](fair_comparisons.md) explain the detailed rules.
