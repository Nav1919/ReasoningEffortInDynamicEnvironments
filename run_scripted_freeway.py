# imports
import json
from datetime import datetime, timezone
from pathlib import Path

import realtimegym


def main():
    # set up the game we want to run
    # v0 is easy, v1 is medium, and v2 is hard
    environment = "Freeway-v0"

    # choose a seed so we can repeat the same starting game
    requested_seed = 0

    # create the environment
    # real_seed is the seed RealtimeGym maps our requested seed to
    # we don't need the renderer yet, so store it as _
    # render=False means we are running without a graphical game display
    env, real_seed, _ = realtimegym.make(
        environment,
        seed=requested_seed,
        render=False,
    )

    # initialize the game and get its first observation
    # observation contains the board, current turn, and structured state
    # done tells us whether the episode has ended
    observation, done = env.reset()

    # find the folder where this Python file is saved
    # this keeps the log location consistent even if we run from another folder
    script_directory = Path(__file__).resolve().parent

    # create a logs folder inside the script's folder
    log_directory = script_directory / "logs"

    # make the folder if it doesn't exist
    # exist_ok=True means an existing folder won't cause an error
    log_directory.mkdir(exist_ok=True)

    # get the current time in UTC for the log filename
    # include microseconds so separate runs have different filenames
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )

    # set the full path for this episode's JSON log
    log_path = log_directory / f"scripted_freeway_{timestamp}.json"

    # initialize the dictionary that will store the entire episode
    # first record the settings so we know how this run was produced
    episode = {
        "environment": environment,
        "requested_seed": requested_seed,
        "real_seed": int(real_seed),

        # record the RealtimeGym commit we installed
        # update this if we change the benchmark version later
        "realtimegym_commit": (
            "3d5b3ef37dafee25ca2e8d2e8d71f5fe842eda7b"
        ),

        # this scripted agent always chooses to move up
        "policy": "always_up",

        # there is no model or independent game clock yet
        # each call to env.step advances the game by one turn
        "timing_mode": "synchronous_scripted",

        # save the starting observation before any actions happen
        "initial_observation": observation,

        # initialize an empty list to hold every step of the episode
        "steps": [],
    }

    # initialize the collision counter
    collisions = 0

    # keep taking actions until the game ends
    while not done:
        # save the observation available before this action
        # later, this will be the information we give the model
        observation_before = observation

        # choose the action
        # U = move up, D = move down, S = stay
        action = "U"

        # apply the action and advance the environment by one turn
        # observation is the new state after the action
        # done tells us whether the episode ended
        # score is the current episode score, not an incremental reward
        # collided tells us whether the player was hit this turn
        observation, done, score, collided = env.step(action)

        # add one collision if collided is True
        # int(True) is 1 and int(False) is 0
        collisions += int(collided)

        # save this step to the episode log
        # storing both observations lets us compare before and after
        episode["steps"].append({
            "turn": int(env.game_turn),
            "observation_before": observation_before,
            "action": action,

            # RealtimeGym returns {} when the episode ends
            # save that empty observation without trying to read its keys
            "observation_after": observation,

            "score": float(score),
            "collision": bool(collided),
            "done": bool(done),
        })

        # print a short update so we can follow the run in the terminal
        # use env.game_turn because the final observation is empty
        print(
            f"Turn {env.game_turn:3d} | "
            f"Action: {action} | "
            f"Score: {score} | "
            f"Collision: {collided}"
        )

    # after the episode ends, save its overall results
    # don't sum the step scores because each is the current episode score
    episode["summary"] = {
        "turns": int(env.game_turn),
        "collisions": collisions,
        "final_score": float(score),
    }

    # some observation values are NumPy scalars
    # JSON can't directly save all NumPy types
    # this helper converts those scalars into regular Python values
    def convert_scalar(value):
        if hasattr(value, "item"):
            return value.item()

        # raise an error for any other unsupported type
        # this helps us catch unexpected values instead of silently changing them
        raise TypeError(
            f"Cannot serialize {type(value).__name__}"
        )

    # open the log file for writing
    # the with block automatically closes it when we're finished
    with log_path.open("w", encoding="utf-8") as file:
        # write the episode dictionary as JSON
        # indent=2 makes the saved file easier to read
        # default calls our helper for values JSON can't normally save
        json.dump(
            episode,
            file,
            indent=2,
            default=convert_scalar,
        )

    # print the final results and the saved file location
    print("\nEpisode finished.")
    env.summary()
    print("Total collisions:", collisions)
    print("Log saved to:", log_path)


# run main when this file is executed directly
# importing this file from another script won't automatically start a game
if __name__ == "__main__":
    main()