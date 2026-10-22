# Check the saved Freeway experiments

First follow the installation steps in the README. Then run:

```sh
python -m unittest discover -v
```

This branch has 43 tests. They run without Ollama or model downloads. They check
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
