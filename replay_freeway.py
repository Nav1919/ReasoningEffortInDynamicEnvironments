"""Verify saved Freeway actions offline against the pinned simulator.

Usage: python replay_freeway.py EPISODE.json[.gz]
Reads a model or scripted log; prints verified turn/collision counts. No model
calls or timing recreation. Regression tests: test_reproducibility.py.
"""
import argparse
import json
import realtimegym
from freeway_study import read_episode
from run_model_freeway import convert_scalar


def plain(value):
    return json.loads(json.dumps(value, default=convert_scalar))


def replay(episode):
    """Recreate the starting seed, then check every saved transition."""
    env, actual, _ = realtimegym.make(episode['environment'],
                                     seed=episode['requested_seed'], render=False)
    observation, _ = env.reset()
    if int(actual) != episode['real_seed'] or plain(observation) != episode['initial_observation']:
        raise ValueError('Starting state differs; check the simulator revision')
    collisions = 0
    for index, step in enumerate(episode['steps'], 1):
        if plain(observation) != step['observation_before']:
            raise ValueError(f'Observation mismatch before turn {index}')
        observation, done, score, collision = env.step(step['action'])
        expected = (step['observation_after'], step['done'], step['score'], step['collision'], step['turn'])
        actual = (plain(observation), bool(done), float(score), bool(collision), int(env.game_turn))
        if actual != expected:
            raise ValueError(f'Transition mismatch at turn {index}')
        collisions += int(collision)
        if done and index != len(episode['steps']):
            raise ValueError('Saved actions continue after termination')
    if collisions != episode['summary']['collisions'] or len(episode['steps']) != episode['summary']['turns']:
        raise ValueError('Summary differs from replayed actions')
    return {'verified_turns': len(episode['steps']), 'collisions': collisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episode')
    args = parser.parse_args()
    print(json.dumps(replay(read_episode(args.episode))))


if __name__ == '__main__':
    main()
