# imports
import argparse
import json
from pathlib import Path

import pygame
import realtimegym


def convert_scalar(value):
    # observations can contain NumPy scalars
    # turn those into regular Python values so they compare against the JSON log
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def as_logged(observation):
    # the log stores tuples as lists and NumPy values as plain numbers
    # round-trip through JSON so replayed observations use the same format
    return json.loads(json.dumps(observation, default=convert_scalar))


def find_latest_log():
    # default to the newest Freeway episode in the logs folder
    log_directory = Path(__file__).resolve().parent / "logs"
    # sort by the timestamp at the end of the name, not the scripted/model prefix
    logs = sorted(
        log_directory.glob("*freeway_*.json"),
        key=lambda path: path.stem.rsplit("_", 1)[-1],
    )
    if not logs:
        raise SystemExit(f"No Freeway logs found in {log_directory}")
    return logs[-1]


def draw_board(env, hit_lane=None, cell=60):
    # draw the board from the environment's internal state
    # the installed package doesn't ship FreewayRender's sprites, so use shapes
    # internal rows run from 0 (goal) to 9 (start); the player crosses at column 4
    surface = pygame.Surface((9 * cell, 10 * cell))
    for row in range(10):
        for column in range(9):
            if row in (0, 9):
                color = (90, 170, 80)
            elif column == 4:
                color = (150, 140, 70)
            else:
                color = (85, 85, 85)
            pygame.draw.rect(surface, color, (column * cell, row * cell, cell, cell))
            pygame.draw.rect(surface, (60, 60, 60), (column * cell, row * cell, cell, cell), 1)

    # each car is [x, row, timer, speed, length]; empty lanes use None
    for x, row, _, speed, length in env.cars:
        if x is None or speed is None:
            continue
        moving_right = speed > 0
        left = (x - length + 1) * cell if moving_right else x * cell
        body = pygame.Rect(left + 3, row * cell + 10, length * cell - 6, cell - 20)
        pygame.draw.rect(surface, (210, 60, 60), body, border_radius=8)

        # point a small triangle in the car's direction of travel
        tip = body.right if moving_right else body.left
        back = tip - 12 if moving_right else tip + 12
        middle = body.centery
        pygame.draw.polygon(
            surface, (255, 255, 255),
            [(tip, middle), (back, middle - 8), (back, middle + 8)],
        )

    # outline the cell where this turn's collision happened
    if hit_lane is not None:
        hit = pygame.Rect(4 * cell, (9 - hit_lane) * cell, cell, cell)
        pygame.draw.rect(surface, (255, 230, 0), hit, 4)

    # the player is the yellow circle; the goal is marked above its column
    center = 4 * cell + cell // 2
    pygame.draw.circle(surface, (255, 255, 255), (center, cell // 2), cell // 5, 3)
    pygame.draw.circle(surface, (250, 210, 40), (center, env.pos * cell + cell // 2), cell // 3)

    font = pygame.font.Font(None, 32)
    label = font.render(f"Turn {env.game_turn}  Score {env.reward}", True, (255, 255, 255))
    surface.blit(label, (10, 10))

    if env.terminal:
        overlay = pygame.Surface(surface.get_size())
        overlay.set_alpha(120)
        surface.blit(overlay, (0, 0))
        message = "GAME OVER" if env.game_turn >= 100 else f"SUCCESS in {env.game_turn} turns"
        end = pygame.font.Font(None, 48).render(message, True, (255, 255, 255))
        surface.blit(end, end.get_rect(center=surface.get_rect().center))
    return surface


def replay_frames(episode):
    # rebuild the game from the logged environment and seed
    # the environment is deterministic, so the logged actions recreate every turn
    env, real_seed, _ = realtimegym.make(
        episode["environment"],
        seed=episode["requested_seed"],
        render=False,
    )
    if real_seed != episode["real_seed"]:
        raise SystemExit(
            f"Log used seed {episode['real_seed']}, but replay mapped to {real_seed}"
        )

    observation, done = env.reset()
    if as_logged(observation) != episode["initial_observation"]:
        raise SystemExit("Replayed starting state doesn't match the log")

    decisions = {
        decision["id"]: decision for decision in episode.get("decisions", [])
    }

    # frame 0 is the starting board before any action
    # each later frame is the board after one logged step
    frames = [{
        "surface": draw_board(env),
        "lines": [f"{Path(episode['log_path']).name}", "Start of episode"],
        "collision": False,
    }]

    for step in episode["steps"]:
        if done:
            raise SystemExit(f"Log continues after the episode ended at turn {env.game_turn}")

        # check the board before the move, then apply the exact logged action
        if as_logged(observation) != step["observation_before"]:
            raise SystemExit(f"State before turn {step['turn']} doesn't match the log")
        observation, done, score, collided = env.step(step["action"])

        # stop if the replay drifts from what was recorded
        mismatches = [
            name for name, replayed, logged in [
                ("turn", int(env.game_turn), step["turn"]),
                ("observation", as_logged(observation), step["observation_after"]),
                ("score", float(score), step["score"]),
                ("collision", bool(collided), step["collision"]),
                ("done", bool(done), step["done"]),
            ]
            if replayed != logged
        ]
        if mismatches:
            raise SystemExit(
                f"Replay doesn't match the log at turn {step['turn']}: "
                + ", ".join(mismatches)
            )

        # describe where this action came from
        # scripted logs have no action source or model decisions
        source = step.get("action_source", episode.get("policy", "scripted"))
        lines = [
            f"Turn {step['turn']} | action {step['action']} | {source}",
            f"Score {step['score']:g} | collision {step['collision']}",
        ]
        decision = decisions.get(step.get("decision_id"))
        if decision is not None:
            lines.append(
                f"Decision {decision['id']} saw turn {decision['observed_turn']} | "
                f"age {decision.get('observation_age_turns')} turns | "
                f"latency {decision.get('latency_seconds', 0):.2f}s"
            )
        elif step.get("pending_decision_id") is not None:
            lines.append(f"Waiting on decision {step['pending_decision_id']}")

        # a collision sends the player back to the start before we draw
        # recover the lane it moved into from the logged state and action
        hit_lane = None
        if step["collision"]:
            moves = {"U": 1, "D": -1}
            start = step["observation_before"]["state"]["player_states"]
            hit_lane = min(max(start + moves.get(step["action"], 0), 0), 9)

        frames.append({
            "surface": draw_board(env, hit_lane),
            "lines": lines,
            "collision": step["collision"],
        })

    if not done:
        frames[-1]["lines"].append("Log ends before the episode finished")
    return frames


def show(frames, seconds_per_turn):
    # draw the game board with a text panel below it
    board_width, board_height = frames[0]["surface"].get_size()
    panel_height = 110
    window = pygame.display.set_mode((board_width, board_height + panel_height))
    pygame.display.set_caption("Freeway replay")
    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

    index = 0
    playing = True
    elapsed = 0.0
    running = True
    while running:
        # space pauses, arrows step one turn, R restarts, escape quits
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    playing = not playing
                elif event.key == pygame.K_RIGHT:
                    playing = False
                    index = min(index + 1, len(frames) - 1)
                elif event.key == pygame.K_LEFT:
                    playing = False
                    index = max(index - 1, 0)
                elif event.key == pygame.K_r:
                    index = 0
                    elapsed = 0.0
                    playing = True

        # advance on a fixed playback clock, not the original wall-clock timing
        elapsed += clock.tick(60) / 1000
        if playing and elapsed >= seconds_per_turn:
            elapsed = 0.0
            if index < len(frames) - 1:
                index += 1
            else:
                playing = False

        frame = frames[index]
        window.fill((30, 30, 30))
        window.blit(frame["surface"], (0, 0))
        status = "playing" if playing else "paused"
        lines = frame["lines"] + [
            f"Frame {index}/{len(frames) - 1} ({status}) | "
            "space pause, arrows step, R restart, Esc quit"
        ]
        for row, text in enumerate(lines):
            color = (255, 90, 90) if frame["collision"] and row == 1 else (230, 230, 230)
            window.blit(
                font.render(text, True, color),
                (10, board_height + 8 + row * 24),
            )
        pygame.display.flip()

    pygame.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Replay a logged Freeway episode in the RealtimeGym GUI."
    )
    parser.add_argument(
        "log", nargs="?", type=Path,
        help="episode log to replay (default: newest Freeway log in logs/)",
    )
    parser.add_argument("--seconds-per-turn", type=float, default=0.5)
    args = parser.parse_args()
    if args.seconds_per_turn <= 0:
        parser.error("seconds per turn must be positive")

    log_path = args.log or find_latest_log()
    with log_path.open(encoding="utf-8") as file:
        episode = json.load(file)
    episode["log_path"] = str(log_path)

    pygame.init()
    frames = replay_frames(episode)
    print(f"Replayed {len(frames) - 1} turns from {log_path}; matches the log.")
    show(frames, args.seconds_per_turn)


# run main when this file is executed directly
if __name__ == "__main__":
    main()
