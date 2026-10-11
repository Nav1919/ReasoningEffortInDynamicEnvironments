# imports
import argparse
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import realtimegym
from pprint import pprint


def convert_scalar(value):
    # observations can contain NumPy scalars
    # turn those into regular Python values before saving or sending JSON
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def post_json(endpoint, payload):
    # send a request to the Ollama server running on our own computer
    request = Request(
        f"http://localhost:11434/api/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def build_prompt(observation, tick_seconds):
    # explain the structured state using the benchmark's coordinate system
    # x=0 is the player's column; y=0 is the start and y=9 is the goal
    # this snapshot won't update while the model generates its response
    return (
        "Your goal is to get to y=9 by choosing one action: U (up), D (down), or S (stay). "
        "While S is a valid action, you should try to go up at least once."
        "You should not stay at y=0"
        "Reach y=9 from y=0 while avoiding cars in lanes y=1 through y=8. "
        "U increases player y by 1; D decreases it by 1; S leaves it unchanged. "
        "The player stays at x=0. player_states is player y. "
        "Each car_states entry is [lane_y, head_x, direction, speed, length]. "
        "Positions, speed, and length use units of 1/12 of a board column. "
        "Speed is the positive distance moved per turn. "
        "For right-moving cars the tail is head_x-length; "
        "for left-moving cars it is head_x+length. Cars wrap around the board. "
        "The player moves before cars move and collisions are checked. "
        "A collision resets the player and traffic to their starting layout. "
        "Score starts at 100 and falls by 1 each turn. "
        "The episode ends on reaching the goal or after 100 turns. "
        f"The game advances approximately every {tick_seconds} seconds, "
        "Your snapshot may be stale when your action is applied."
        "Return only U, D, or S.\n\n"
        "Observation:\n"
        + json.dumps(observation, default=convert_scalar)
    )


def request_action(payload, probe_delay):
    # this function runs in a worker thread
    # only the main thread touches the environment
    started = time.perf_counter()
    try:
        if probe_delay is not None:
            # this is a clock test, not a model response
            # pretend an agent needs time to decide, then choose U
            time.sleep(probe_delay)
            response = {"message": {"content": "U"}, "done_reason": "stop"}
        else:
            response = post_json("chat", payload)
        error = None
    except Exception as exception:
        # a failed model request shouldn't stop the game clock
        # save the error and fall back to S when this request finishes
        response = None
        error = f"{type(exception).__name__}: {exception}"
    finished = time.perf_counter()
    return response, error, started, finished


def main():
    # command-line options let us change modes without editing the file
    parser = argparse.ArgumentParser()
    parser.add_argument("--thinking", choices=["off", "on"], default="off")
    parser.add_argument("--tick-seconds", type=float, default=1.0)
    parser.add_argument("--seed", type=int, choices=range(8), default=0)
    parser.add_argument("--model", default="qwen3:4b-q4_K_M")
    parser.add_argument("--probe-delay", type=float, default=None)
    args = parser.parse_args()
    if args.tick_seconds <= 0 or (
        args.probe_delay is not None and args.probe_delay < 0
    ):
        parser.error("tick seconds must be positive; probe delay cannot be negative")

    # record the actual model metadata before starting the game clock
    # fail here if Ollama isn't running or the requested model is missing
    # the delayed scripted probe doesn't need Ollama
    model_metadata = None
    if args.probe_delay is None:
        model_metadata = post_json("show", {"model": args.model})

    env, real_seed, _ = realtimegym.make("Freeway-v0", seed=args.seed, render=False)
    observation, done = env.reset()
    log_directory = Path(__file__).resolve().parent / "logs"
    log_directory.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    log_path = log_directory / f"model_freeway_{timestamp}.json"
    episode = {
        "environment": "Freeway-v0",
        "requested_seed": args.seed,
        "real_seed": int(real_seed),
        "settings": vars(args),
        "model_metadata": model_metadata,
        "policy": "delayed_scripted_probe" if args.probe_delay is not None else "ollama",
        "timing_mode": "wall_clock_with_worker_inference",
        "default_action": "S",
        "initial_observation": copy.deepcopy(observation),
        "decisions": [],
        "steps": [],
    }

    # use one worker and allow only one outstanding request at a time
    # a ready action is applied once, at the next game tick
    worker = ThreadPoolExecutor(max_workers=1)
    pending = None
    decision = None
    ready = None
    collisions = 0
    started_episode = time.perf_counter()
    next_tick = started_episode + args.tick_seconds
    error = None

    def collect_response():
        # collect a completed response without changing the environment
        response, request_error, started, finished = pending.result()
        # pprint(response)
        content = (response or {}).get("message", {}).get("content", "")
        action = content.strip().upper()
        complete = (response or {}).get("done_reason") == "stop"
        valid = request_error is None and complete and action in {"U", "D", "S"}
        decision.update({
            "response": response,
            "error": request_error,
            "latency_seconds": finished - started,
            "request_started_seconds": started - started_episode,
            "response_finished_seconds": finished - started_episode,
            "response_collected_turn": int(env.game_turn),

            # count ticks that happened inside the measured request interval
            # this is stronger evidence than just checking total latency
            "ticks_during_request": sum(
                started - started_episode
                <= step["elapsed_seconds"]
                <= finished - started_episode
                for step in episode["steps"]
            ),
            "valid_action": valid,
            "parsed_action": action if valid else "S",
        })

        # reject prose, invalid actions, and truncated responses
        # don't search the thinking text for a letter that looks like an action
        print(
            f"Decision {decision['id']} | saw turn {decision['observed_turn']} | "
            f"collected at turn {env.game_turn} | "
            f"action {decision['parsed_action']} | valid {valid}",
            flush=True,
        )

    try:
        while not done:
            if pending is None and ready is None:
                # freeze a copy of the state the model actually receives
                # later turns won't silently change this saved observation
                snapshot = copy.deepcopy(observation)
                payload = {
                    "model": args.model,
                    "messages": [{
                        "role": "user",
                        "content": build_prompt(snapshot, args.tick_seconds),
                    }],
                    "think": args.thinking == "on",
                    "stream": False,
                    "keep_alive": "5m",
                    "options": {
                        "temperature": 0.6,
                        "seed": 0,
                        "num_predict": 2048,
                        "num_ctx": 4096,
                    },
                }
                decision = {
                    "id": len(episode["decisions"]),
                    "observed_turn": int(env.game_turn),
                    "observation": snapshot,
                    "request": payload,
                    "submitted_seconds": time.perf_counter() - started_episode,
                }
                episode["decisions"].append(decision)
                pending = worker.submit(request_action, payload, args.probe_delay)

            if pending is not None and pending.done():
                collect_response()
                ready = decision
                pending = None

            now = time.perf_counter()
            if now >= next_tick:
                # S is the waiting action even after a previous U or D
                # don't keep repeating the last model action during inference
                action = ready["parsed_action"] if ready is not None else "S"
                source = "model" if ready is not None else "waiting_default"
                if args.probe_delay is not None and ready is not None:
                    source = "probe"
                if ready is not None:
                    # age counts turns already elapsed before applying the action
                    ready["applied_turn"] = int(env.game_turn) + 1
                    ready["observation_age_turns"] = (
                        int(env.game_turn) - ready["observed_turn"]
                    )
                    ready["status"] = "applied"

                before = copy.deepcopy(observation)
                previous_score = float(env.reward)
                observation, done, score, collided = env.step(action)
                collisions += int(collided)
                episode["steps"].append({
                    "turn": int(env.game_turn),
                    "elapsed_seconds": now - started_episode,
                    "scheduler_lag_seconds": now - next_tick,
                    "observation_before": before,
                    "action": action,
                    "action_source": source,
                    "decision_id": ready["id"] if ready is not None else None,
                    "pending_decision_id": (
                        decision["id"] if pending is not None else None
                    ),
                    "observation_after": copy.deepcopy(observation),
                    "score": float(score),
                    "score_change": float(score) - previous_score,
                    "collision": bool(collided),
                    "done": bool(done),
                })
                print(
                    f"Turn {env.game_turn:3d} | {action} | {source} | "
                    f"Score {score} | Collision {collided}",
                    flush=True,
                )
                ready = None

                # don't run a burst of catch-up turns after a scheduler delay
                # save any lag so we can assess the actual clock behavior
                next_tick = time.perf_counter() + args.tick_seconds
            else:
                # briefly yield CPU while keeping an eye on the next game tick
                time.sleep(min(0.01, next_tick - now))
    except BaseException as exception:
        error = f"{type(exception).__name__}: {exception}"
        raise
    finally:
        # save the episode even if a request is still running at its end
        # the game stops immediately; a late response cannot act on it

        # moving up from y=8 reaches the goal, including on turn 100
        last_step = episode["steps"][-1] if episode["steps"] else None
        reached_goal = bool(
            done and last_step and last_step["action"] == "U"
            and last_step["observation_before"]["state"]["player_states"] == 8
        )
        episode["summary"] = {
            "episode_ended": bool(done),
            "turns": int(env.game_turn),
            "collisions": collisions,
            "final_score": float(env.reward),
            "success": reached_goal,
            "elapsed_seconds": time.perf_counter() - started_episode,
            "error": error,
        }

        def save_log():
            with log_path.open("w", encoding="utf-8") as file:
                json.dump(episode, file, indent=2, default=convert_scalar)

        if pending is not None:
            decision["status"] = "pending_when_episode_ended"
        save_log()
        print("\nEpisode log saved to:", log_path, flush=True)
        try:
            if pending is not None:
                # wait for the outstanding HTTP call so we can log its response
                # this wait is after the game has ended, not a paused game turn
                print(
                    "Waiting for the outstanding request; its action will be discarded.",
                    flush=True,
                )
                collect_response()
                decision["status"] = "discarded_after_episode"
            save_log()
        finally:
            worker.shutdown(wait=True)

    env.summary()


if __name__ == "__main__":
    main()