# Check the saved Freeway experiments

First follow the installation steps in the README. Then run:

```sh
python -m unittest discover -v
```

The saved-Freeway checks run without Ollama or model downloads. They check
the game rules, action parsing, timing calculations, and all 15 saved game replays.
They also rebuild the saved tables in a temporary folder and check every published
file against its saved checksum. Deliberately damaged records must fail replay.
`tests/test_decision_models.py` adds offline checks for the shared Ollama
reasoning and instant-model clients and strict action parsing.
`tests/test_observer_agent.py` stubs that client and checks the observer
prompt asks for reasoning only.
`tests/test_actor_agent.py` stubs the same client and checks the actor
asks for only U/D/S, rejects prose or truncated replies, and falls back to S.
`tests/test_experiment_runner.py` checks the runner-owned reveal schedule
(`x=10`, `time_pressure=3` → prefixes of length 3, 6, 9, 10; empty or
short traces do not invent extra steps) using the named `whitespace`
approximation, and that `build_actor_context` includes or excludes the
revealed prefix and live observation by `context_mode`. It also runs the
episode loop with stub observer/actor objects: `observation` never calls
`think`; the inner loop uses the actual token count; ending mid-trace
does not call `act` again; a stubbed episode writes the expected JSON
keys; and a RealtimeGym reset/step smoke uses those stubs. Those tests
also do not call Ollama:

```sh
python -m unittest tests.test_decision_models tests.test_observer_agent tests.test_actor_agent tests.test_experiment_runner -v
```

For example, changing a saved collision from true to false must be detected.
These checks confirm that the saved results can be checked. They do not show that
the AI plays well. The same command runs automatically for each pull request.
