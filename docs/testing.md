# Check the saved Freeway experiments

First follow the installation steps in the README. Then run:

```sh
python -m unittest discover -v
```

This branch has 14 tests. They run without Ollama or model downloads. They check
the game rules, action parsing, timing calculations, and all 15 saved game replays.
They also rebuild the saved tables in a temporary folder and check every published
file against its saved checksum. Deliberately damaged records must fail replay.

For example, changing a saved collision from true to false must be detected.
These checks confirm that the saved results can be checked. They do not show that
the AI plays well. The same command runs automatically for each pull request.
