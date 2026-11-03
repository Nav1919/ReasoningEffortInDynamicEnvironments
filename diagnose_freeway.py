"""Compare three prompts on four reachable frozen Freeway states via Ollama.

Usage: python diagnose_freeway.py. Output: logs/controlled_freeway_TIMESTAMP.json.
Shared request/parser helpers are checked in test_model_freeway.py; historical
results and limitations are in docs/freeway_diagnosis.md. No live episode runs.
"""
# Compare prompts on reachable states without calling these model episodes.
# Every state is produced by real environment steps, never invented coordinates.
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import realtimegym
from run_model_freeway import build_request, request_action, parse_action, convert_scalar, post_json


def main():
    # Timestamped files preserve earlier trials, including failed comparisons.
    directory = Path(__file__).resolve().parent / 'logs'
    directory.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = directory / f'controlled_freeway_{stamp}.json'
    log = {'model_metadata': post_json('show', {'model': 'qwen3:4b-q4_K_M'}),
           'trials': [], 'kind': 'reachable_state_diagnostic_not_live_episode'}

    def save():
        path.write_text(json.dumps(log, indent=2, default=convert_scalar))

    # Warm the weights before timing any of the controlled trials.
    warm = {'model': 'qwen3:4b-q4_K_M', 'messages': [{'role': 'user',
            'content': 'Return only S.'}], 'think': False, 'stream': False}
    response, error, start, end = request_action(warm, None)
    log['warmup'] = dict(request=warm, response=response, error=error, latency_seconds=end-start)
    save()
    for strategy, board in [('original', 'full'), ('progress', 'full'), ('progress', 'structured')]:
        for prefix in ['', 'U', 'UU', 'UUU']:
            env, _, _ = realtimegym.make('Freeway-v0', seed=0, render=False)
            observation, _ = env.reset()
            for action in prefix:
                observation, _, _, collided = env.step(action)
                assert not collided
            # Counterfactual checks establish what each immediate action actually
            # does in this installed environment. These checks never guide pilots.
            transitions = {}
            for action in ['U', 'D', 'S']:
                trial_env = copy.deepcopy(env)
                after, done, score, collision = trial_env.step(action)
                transitions[action] = dict(observation=after, done=done, score=score, collision=collision)
            assert transitions['U']['collision'] == (prefix == 'UUU')
            args = SimpleNamespace(model='qwen3:4b-q4_K_M', tick_seconds=1.0,
                                   prompt=strategy, board=board, thinking='off')
            payload = build_request(observation, args)
            response, error, start, end = request_action(payload, None)
            parsed = parse_action(response, error)
            applied = parsed or 'S'
            log['trials'].append(dict(strategy=strategy, board=board, prefix=prefix,
                observation=observation, request=payload, response=response, error=error,
                parsed_action=parsed, fallback_action=None if parsed else 'S',
                latency_seconds=end-start, validated_transitions=transitions,
                outcome=transitions[applied]))
            save()
            print(strategy, board, repr(prefix), parsed, round(end-start, 3), flush=True)


if __name__ == '__main__':
    main()
