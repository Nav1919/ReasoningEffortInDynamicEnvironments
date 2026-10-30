# Freeway setup

## Working setup

Our first scripted run used:

- Python 3.13.2 on macOS
- RealtimeGym commit:
  `3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`
- Environment: `Freeway-v0`
- Requested seed: `0`
- Actual environment seed: `1000`
- Policy: always move up

## Install

From the project root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-freeway.txt
```

The requirements files record the package versions from our working
macOS setup. Installation on other machines still needs verification.

## Run a scripted episode

From the project root:

```bash
python run_scripted_freeway.py
```

The script saves a timestamped JSON file in `logs/`.

Each step records:

- The observation before the action
- The chosen action
- The observation after the action
- The current episode score
- Whether a collision occurred
- Whether the episode ended

## First observed result

The always-up policy finished after 100 turns with:

- 25 collisions
- Final score of 0
- No successful crossing

This verifies the environment and logging, rather than demonstrating
a useful game-playing policy.

## Timing

The current script advances the game only when `env.step()` is called.
It does not yet advance the game during model inference.

## Terminal observations

RealtimeGym returns an empty observation dictionary when the episode ends.
The script therefore uses `env.game_turn` when printing the terminal step.