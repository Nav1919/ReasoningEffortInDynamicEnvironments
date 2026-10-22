# Check the saved Freeway experiments

First follow the installation steps in the README. Then run:

```sh
python -m unittest discover -v
```

This branch has 78 tests. They run without Ollama or model downloads. They check
the game rules, action parsing, timing calculations, and all 15 saved game replays.
They also rebuild the saved tables in a temporary folder and check every published
file against its saved checksum. Deliberately damaged records must fail replay.

For example, changing a saved collision from true to false must be detected.
These checks confirm that the saved results can be checked. They do not show that
the AI plays well. The same command runs automatically for each pull request.

## Check fair comparison settings

The added tests check that models receive the same game instructions. Only the
thinking setting may change. They reject a wrong model version, unsupported
thinking settings, duplicate starts, and missing settings. They also confirm
that `1` and `1.0` mean the same interval and that validation does not edit inputs.

```sh
python -m unittest test_config_boundaries test_experiment_config test_experiment_identity test_comparison_requests test_experiment_starts test_model_provenance test_model_capabilities test_reasoning_modes test_run_provenance -v
```

Model checks use fake metadata. They never ask a model to answer a question.

## Check execution and failures

The tests run saved plans with a fake model. They check successful answers,
invalid answers, interrupted runs, timeouts, and a model that cannot load. They
also test the live game loop with a controlled clock. Real model calls and waits
are replaced, so these tests cost no inference time.

```sh
python -m unittest test_comparison_failures test_comparison_execution test_frozen_comparison test_controlled_runner test_native_preload test_comparison_summary test_comparison_metrics test_comparison_commands test_comparison_plan test_plan_consistency test_decision_records test_run_records -v
```

For example, if the first answer times out, the next question must not be sent.
The failed question and all unrun questions must still appear in the saved files.
A changed plan is rejected before any request. Results made with different code
cannot be silently mixed. A 600-second loading limit does not extend the
180-second answer limit. The native plan asks exactly 18 measured questions.
