# Understanding Freeway

## What are we trying to do?

Our agent controls a player trying to cross eight lanes of moving traffic.

The player starts below the road and moves upward toward the goal. It can
move up, move down, or stay in place. Cars move horizontally across the lanes.

The main challenge is choosing when to move. A lane that looks clear now
might contain a car by the time the action takes effect.

## What is a state? What is an observation?

A state describes the game at a particular moment: where the player is,
where the cars are, and how they are moving.

An observation is the information the environment gives our agent about
that moment.

Freeway gives us both a text drawing of the board and structured values
that our code can read.

For example, our initial observation contains:

```python
{
    "state_string": "...text drawing of the board...",
    "game_turn": 0,
    "state": {
        "player_states": 0,
        "car_states": [
            (1, 48, "right", 12, 11),
            (1, 0, "right", 12, 11),
            (2, -48, "right", 48, 47),
            (3, 48, "left", 24, 23),
            (4, -48, "right", 12, 11),
            (4, -12, "right", 12, 11),
            (4, 24, "right", 12, 11),
            (5, 48, "right", 4, 11),
            (6, 48, "right", 4, 11),
            (6, 12, "right", 4, 11),
            (6, -24, "right", 4, 11),
            (7, 48, "right", 12, 11),
            (7, 0, "right", 12, 11),
            (8, 48, "right", 12, 11),
            (8, 0, "right", 12, 11),
        ],
        "game_turn": 0,
    },
}
```

The car list above is the full structured starting state from our first run.
The board string is abbreviated here because it draws the same situation.

Read this observation as:

- No turns have passed yet.
- The player is at the starting position.
- There are multiple cars across eight lanes.
- Each car entry describes its location, direction, speed, and length.

## Where is the player?

The player’s vertical position is stored in:

```python
observation["state"]["player_states"]
```

The positions mean:

| Position | Meaning |
|---|---|
| 0 | Starting area below the road |
| 1–8 | Traffic lanes, numbered from bottom to top |
| 9 | Goal above the road |

Moving up increases the player's progress. Moving down decreases it.

The player stays at the same horizontal crossing point, represented as
horizontal coordinate 0 in the structured state.

The text drawing uses `P` to mark the player.

One detail matters when checking the result: when the player reaches the
goal, the implementation resets its position and returns an empty terminal
observation. We therefore need to record success from the transition into
the goal, rather than look for position 9 in the final observation.

## How do we read a car entry?

Each car is represented by:

```python
(lane, head_position, direction, speed, length)
```

Take this example:

```python
(3, 48, "left", 24, 23)
```

It describes a car:

- In lane 3
- With its front at horizontal position 48
- Moving left
- Moving 24 coordinate units per turn
- Spanning 23 coordinate units

Because the player crosses at horizontal position 0, this car is to the
right of the crossing point and moving toward it.

As a simple illustration, moving left by 24 units twice would take its head
from 48 to 24 to 0. Actual collision predictions must also account for the
car's length, boundary behavior, and the game's update rules.

The car's body extends behind its front:

```python
# a right-moving car extends toward the left
tail_position = head_position - length

# a left-moving car extends toward the right
tail_position = head_position + length
```

This matters because the player can be hit by the car's body even when its
front is no longer at the crossing point.

The numbers use the environment's coordinate system. They are not pixels
or column numbers from the text drawing.

## What actions can the agent take?

The agent returns one of three strings:

| Action | What it does |
|---|---|
| `"U"` | Move up one lane toward the goal |
| `"D"` | Move down one lane toward the start |
| `"S"` | Stay at the current position |

For example:

```python
action = "U"
observation, done, score, collided = env.step(action)
```

This advances the game by one turn and returns the result.

Staying still only keeps the player in place. Cars still move, so staying
in a traffic lane can also lead to a collision.

## What happens during one turn?

In this implementation:

1. The player moves according to its action.
2. If it reaches the goal, the episode ends.
3. Otherwise, the cars update their positions.
4. The environment checks for collisions.
5. It checks whether the 100-turn limit has been reached.

The order matters. Our agent needs to consider where cars will be after
they move, not just where they appear in the observation.

If a collision happens, the player returns to the start.

After a collision that does not end the episode, the environment also
restores the starting traffic arrangement using the same seed. The elapsed
turns and score are preserved.

That is why our always-up agent keeps repeating the same failure.

## What is a trajectory?

A trajectory is the sequence of observations, actions, and outcomes across
an episode.

A single observation answers:

> What does the game look like right now?

A trajectory answers:

> What did the agent see, what did it do, and what happened over time?

The first four turns of our actual run looked like this:

| Turn | Player position before | Action | Player position after | Collision | Score |
|---|---:|---|---:|---|---:|
| 1 | 0 | U | 1 | No | 99 |
| 2 | 1 | U | 2 | No | 98 |
| 3 | 2 | U | 3 | No | 97 |
| 4 | 3 | U | 0 | Yes | 96 |

The player made progress for three turns. On the fourth turn, it tried to
enter lane 4 and collided, returning to the start.

Our script kept choosing U, so this pattern repeated until the episode ended.

The table is a shortened view of the trajectory. Our JSON log also saves
the full observations before and after each action, including every car.

A logged step has this structure:

```python
{
    "turn": 4,
    "observation_before": {
        # full observation from turn 3
    },
    "action": "U",
    "observation_after": {
        # full observation from turn 4, after the collision
    },
    "score": 96.0,
    "collision": True,
    "done": False,
}
```

The comments above stand in for the full observation dictionaries.
The actual JSON file contains their values.

## How does scoring work?

The score starts at 100 and decreases by one each turn.

For example:

- Turn 1: score 99
- Turn 4: score 96
- Turn 100: score 0

A faster successful crossing earns a higher final score.

The value returned by `env.step()` is the current episode score. It is
not a new reward to add to the previous values.

For our first run, the result was:

```python
{
    "turns": 100,
    "collisions": 25,
    "final_score": 0.0,
}
```

The agent did not cross successfully.

## When does an episode end?

An episode ends when the player reaches the goal or when 100 turns have passed.

The `done` value tells us that the episode ended, but does not by itself
tell us which outcome occurred.

A crossing on turn 100 also has a score of 0, so score alone cannot
distinguish every success from a timeout.

For this implementation, a terminal U action taken from player position 8
means the player reached the goal. We will use that transition to record
success explicitly in our runner.

At the end of an episode, RealtimeGym returns:

```python
observation = {}
done = True
```

Our code must check `done` before trying to read fields from that observation.

## How do we start and step the game?

Start a new episode:

```python
observation, done = env.reset()
```

Take one action:

```python
observation, done, score, collided = env.step(action)
```

The returned values tell us:

| Value | Meaning |
|---|---|
| `observation` | What the game looks like after the turn, or `{}` at termination |
| `done` | Whether the episode ended |
| `score` | The current episode score |
| `collided` | Whether a collision happened during this turn |

## Does the game move while the model thinks?

Not automatically.

The game advances when our program calls `env.step()`. Simply waiting
for a model response does not move the cars.

Our current scripted runner does this:

1. Choose U.
2. Advance the game one turn.
3. Repeat.

Our real-time runner will instead:

1. Capture an observation and send it to the model.
2. Keep advancing the game at a configured interval while the response is pending.
3. Use S as the default action during that wait.
4. Apply the model's action when it becomes available.
5. Record how much the environment advanced since the original observation.

For example, the model might receive an observation from turn 10, but its
action might only be applied at turn 13. The cars may have moved substantially
during that gap.

This is the timing problem our reasoning-effort router will study.

## Version these notes describe

RealtimeGym commit:

`3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b`