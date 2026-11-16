# This file prepares the same Freeway questions for every model and saves each response.
# Use prepare, preview, simulate, or import to work offline; real requests need an explicitly approved budget.
# Run python run_stage_a.py --help for commands and python -m unittest test_stage_a -v for checks.
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import time
from collections import Counter
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from stage_a import FORMATS, VERSION, make_prompt, make_questions, read_scene, render_scene


ROOT = Path(__file__).resolve().parent


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def read_rows(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_row(path, row):
    with path.open('a') as stream:
        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def write_rows(path, rows):
    with path.open('x') as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')


def load_settings(path):
    settings = json.loads(path.read_text())
    if type(settings['count']) is not int or settings['count'] <= 0:
        raise ValueError('count must be a positive integer')
    for field in ('formats', 'sampling_seeds', 'models'):
        if not settings[field]:
            raise ValueError(f'{field} cannot be empty')
    if len(set(settings['formats'])) != len(settings['formats']) or not set(settings['formats']) <= set(FORMATS):
        raise ValueError('Use unique supported formats')
    seeds = settings['sampling_seeds']
    if any(type(seed) is not int for seed in seeds) or len(set(seeds)) != len(seeds):
        raise ValueError('Use unique integer sampling seeds')
    ids = [model['id'] for model in settings['models']]
    if len(ids) != len(set(ids)):
        raise ValueError('Model condition IDs must be unique')
    for model in settings['models']:
        if model['backend'] not in ('synthetic', 'ollama', 'openai_compatible'):
            raise ValueError('Supported backends: synthetic, ollama, openai_compatible')
    return settings


def choose_situations(situations, count, seed):
    if not 0 < count <= len(situations):
        raise ValueError('Not enough distinct situations; do not duplicate rare cases')
    pool = sorted(situations, key=lambda s: s['id'])
    random.Random(seed).shuffle(pool)
    categories, lanes, starts = Counter(), Counter(), Counter()
    selected = []
    while len(selected) < count:
        index = min(range(len(pool)), key=lambda i: (
            categories[pool[i]['category']],
            lanes[pool[i]['observation']['state']['player_states']],
            starts[pool[i]['actual_seed']],
        ))
        situation = pool.pop(index)
        selected.append(situation)
        categories[situation['category']] += 1
        lanes[situation['observation']['state']['player_states']] += 1
        starts[situation['actual_seed']] += 1
    return selected


def prepare(config_path, folder):
    from freeway_scenarios import digest, load, plain, restore
    from freeway_study import internal_state
    settings = load_settings(config_path)
    bank_path = Path(settings['bank'])
    if not bank_path.is_absolute():
        bank_path = ROOT / bank_path
    bank = load(bank_path)
    selected = choose_situations(bank['scenarios'], settings['count'], settings['selection_seed'])
    labels, requests, states = [], [], []
    for situation in selected:
        game = restore(situation)
        if (digest(internal_state(game)) != situation['state_sha256']
                or plain(game.observe()) != situation['observation']):
            raise ValueError(f"Saved state changed: {situation['id']}")
        scene = read_scene(situation['observation'])
        if len(scene['cars']) == 0:
            raise ValueError('The five-probe experiment needs at least one car in each selected scene')
        scene_id = str(situation['id'])
        states.append(dict(situation_id=scene_id, scene=scene))
        questions = make_questions(scene, int(fingerprint([settings['question_seed'], scene_id])[:16], 16))
        if settings['include_actions']:
            answer = situation['answer']
            entry = answer['by_horizon'][str(answer['horizon'])]
            questions.append(dict(probe='action', text='Which action should the player take?',
                                  answer={'action': entry['best_first_actions']},
                                  safe_actions=entry['safe_first_actions'], schema='{"action": "U", "D", or "S"}'))
        for question in questions:
            question_id = fingerprint([scene, question, VERSION])
            labels.append(dict(question_id=question_id, situation_id=scene_id,
                               category=situation['category'], start=situation['actual_seed'],
                               lane=scene['player']['lane'], question=question))
            public = {key: question[key] for key in ('probe', 'text', 'schema')}
            for name in settings['formats']:
                prompt = make_prompt(render_scene(scene, name), public)
                for model in settings['models']:
                    for seed in settings['sampling_seeds']:
                        request = dict(question_id=question_id, situation_id=scene_id,
                                       format=name, probe=question['probe'], prompt=prompt,
                                       model=model, seed=seed, version=VERSION)
                        request['request_id'] = fingerprint(request)
                        requests.append(request)
    random.Random(settings['order_seed']).shuffle(requests)
    folder.mkdir(parents=True, exist_ok=False)
    write_rows(folder / 'states.jsonl', states)
    write_rows(folder / 'questions.jsonl', labels)
    write_rows(folder / 'requests.jsonl', requests)
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except subprocess.CalledProcessError:
        commit = None
    files = ('states.jsonl', 'questions.jsonl', 'requests.jsonl')
    manifest = dict(version=VERSION, settings=settings, source_commit=commit,
                    source_hashes={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                   for name in ('stage_a.py', 'freeway_observations.py', 'run_stage_a.py')},
                    bank_sha256=hashlib.sha256(bank_path.read_bytes()).hexdigest(),
                    bank_metadata=bank['metadata'], request_count=len(requests),
                    selected_ids=[s['id'] for s in selected],
                    category_counts=dict(Counter(s['category'] for s in selected)),
                    lane_counts=dict(Counter(str(s['observation']['state']['player_states']) for s in selected)),
                    start_counts=dict(Counter(str(s['actual_seed']) for s in selected)),
                    files={name: hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in files},
                    note='Development states; no real models have been run by preparation.')
    (folder/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def load_run(folder):
    manifest = json.loads((folder/'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        if hashlib.sha256((folder/name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Prepared file changed: {name}')
    requests = read_rows(folder/'requests.jsonl')
    if len(requests) != manifest['request_count']:
        raise ValueError('Prepared request count changed')
    return manifest, requests


def validate_response(row, request_ids):
    if row['request_id'] not in request_ids:
        raise ValueError('Response refers to an unknown request')
    if row.get('status') not in ('started', 'completed', 'error'):
        raise ValueError('Unknown response status')
    if type(row.get('synthetic')) is not bool:
        raise ValueError('Every response must explicitly identify whether it is synthetic')
    if row['status'] == 'completed' and not isinstance(row.get('text'), str):
        raise ValueError('Completed responses need text')
    for name in ('input_tokens', 'output_tokens', 'elapsed_seconds'):
        value = row.get(name)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError(f'Invalid {name}')


def import_responses(folder, path):
    _, requests = load_run(folder)
    ids = {r['request_id'] for r in requests}
    rows = read_rows(path)
    existing = read_rows(folder/'responses.jsonl')
    attempts = {r['attempt_id'] for r in existing if r.get('status') != 'started'}
    completed = {r['request_id'] for r in existing if r.get('status') == 'completed'}
    modes = {r['synthetic'] for r in existing}
    for row in rows:
        validate_response(row, ids)
        if not isinstance(row.get('attempt_id'), str):
            raise ValueError('Imported responses need an attempt_id')
        key = row['attempt_id']
        modes.add(row['synthetic'])
        if len(modes) > 1:
            raise ValueError('Keep synthetic and real responses in separate folders')
        if row['status'] == 'completed':
            if row['request_id'] in completed:
                raise ValueError('Do not replace a completed answer with another attempt')
            completed.add(row['request_id'])
        if key in attempts:
            raise ValueError('Duplicate imported attempt')
        if row['status'] != 'started':
            attempts.add(key)
    for row in rows:
        append_row(folder/'responses.jsonl', row)
    return len(rows)


def test_response(request, question, profile):
    choice = int(request['request_id'][:8], 16) % 5 if profile == 'mixed' else 0
    if choice == 4:
        return dict(status='error', text=None, error='Synthetic connection failure')
    if profile == 'malformed' or choice == 3:
        text = 'not an answer'
    else:
        answer = dict(question['answer'])
        if question['probe'] == 'action':
            answer = {'action': next(iter(answer['action']), 'S')}
        if profile == 'wrong' or choice == 2:
            if question['probe'] == 'occupancy':
                answer['occupied'] = not answer['occupied']
            elif question['probe'] == 'nearest':
                answer['cars'] = ['not_a_car']
            elif question['probe'] == 'counting':
                answer['count'] += 1
            elif question['probe'] == 'localization':
                answer['head_x'] += 12
            elif question['probe'] == 'motion':
                answer['speed'] += 1
            else:
                answer['action'] = next((a for a in 'UDS' if a not in question['answer']['action']), 'S')
        text = json.dumps(answer)
    return dict(status='completed', text=text, error=None)


def ask_model(request, timeout):
    model = request['model']
    endpoint = model['endpoint'].rstrip('/')
    url = urlsplit(endpoint)
    if url.scheme not in ('http', 'https') or url.username or url.password or url.query or url.fragment:
        raise ValueError('Use an HTTP(S) endpoint without embedded credentials or query strings')
    headers = {'Content-Type': 'application/json'}
    if model.get('api_key_env'):
        headers['Authorization'] = 'Bearer ' + os.environ[model['api_key_env']]
    messages = [{'role': 'user', 'content': request['prompt']}]
    if model['backend'] == 'ollama':
        path = '/api/chat'
        payload = dict(model=model['name'], messages=messages, stream=False,
                       options=dict(seed=request['seed'], temperature=model['temperature'],
                                    num_predict=model['max_output_tokens'], num_ctx=model['context_tokens']))
        if 'thinking' in model:
            payload['think'] = model['thinking']
    elif model['backend'] == 'openai_compatible':
        if 'thinking' in model:
            raise ValueError('Thinking control must be verified for this server before adding support')
        path = '/chat/completions'
        payload = dict(model=model['name'], messages=messages, seed=request['seed'],
                       temperature=model['temperature'], max_tokens=model['max_output_tokens'])
    else:
        raise ValueError('This backend cannot make real requests')
    with urlopen(Request(endpoint + path, data=json.dumps(payload).encode(), headers=headers), timeout=timeout) as response:
        raw = json.load(response)
    if model['backend'] == 'ollama':
        text = raw['message']['content']
        usage = dict(input_tokens=raw.get('prompt_eval_count'), output_tokens=raw.get('eval_count'))
        finish = raw.get('done_reason')
    else:
        text = raw['choices'][0]['message']['content']
        usage = dict(input_tokens=raw.get('usage', {}).get('prompt_tokens'),
                     output_tokens=raw.get('usage', {}).get('completion_tokens'))
        finish = raw['choices'][0].get('finish_reason')
    return dict(status='completed', text=text, raw=raw, finish_reason=finish, error=None, **usage)


def execute(folder, profile=None, limit=None):
    manifest, requests = load_run(folder)
    synthetic = profile is not None
    history = read_rows(folder/'responses.jsonl')
    if any(row['synthetic'] != synthetic for row in history):
        raise ValueError('Keep synthetic and real responses in separate prepared folders')
    budget = manifest['settings']['real_execution']
    if not synthetic:
        if budget.get('approved') is not True or any(budget.get(key, 0) <= 0 for key in ('max_requests', 'max_seconds', 'max_output_tokens')):
            raise ValueError('Real execution needs an explicitly approved request, time, and output-token budget')
        for request in requests:
            model = request['model']
            for key in ('name', 'identity', 'family', 'quantization', 'temperature', 'max_output_tokens', 'context_tokens', 'endpoint'):
                if key not in model:
                    raise ValueError(f'Model needs {key}')
            if model.get('seed_supported') is not True:
                raise ValueError('Verify server seed support before running repeated-seed comparisons')
            if len(request['prompt']) + model['max_output_tokens'] + 128 > model['context_tokens']:
                raise ValueError('Prompt exceeds conservative context precheck; verify tokenizer before running')
    labels = {row['question_id']: row['question'] for row in read_rows(folder/'questions.jsonl')} if synthetic else {}
    done = {row['request_id'] for row in history if row['status'] == 'completed'}
    attempted = {row['request_id'] for row in history}
    attempt_count = len({row['attempt_id'] for row in history})
    by_attempt = {}
    request_by_id = {r['request_id']: r for r in requests}
    for row in history:
        by_attempt.setdefault(row['attempt_id'], []).append(row)
    reserved_tokens = sum(request_by_id[rows[0]['request_id']]['model'].get('max_output_tokens', 0)
                          for rows in by_attempt.values())
    elapsed_before = sum(next((r.get('elapsed_seconds', 120) for r in rows if r['status'] != 'started'), 120)
                         for rows in by_attempt.values())
    started, added = time.monotonic(), 0
    stop_reason = 'complete'
    for request in requests:
        if request['request_id'] in done or request['request_id'] in attempted:
            continue
        if limit is not None and added >= limit:
            stop_reason = 'request limit'
            break
        reserved = request['model'].get('max_output_tokens', 0)
        remaining = budget['max_seconds'] - elapsed_before - (time.monotonic() - started) if not synthetic else 60
        if not synthetic and (attempt_count >= budget['max_requests'] or remaining <= 0 or reserved_tokens + reserved > budget['max_output_tokens']):
            stop_reason = 'approved budget reached'
            break
        attempt_id = fingerprint([request['request_id'], time.time_ns()])
        base = dict(request_id=request['request_id'], attempt_id=attempt_id, synthetic=synthetic)
        append_row(folder/'responses.jsonl', dict(base, status='started', reserved_output_tokens=reserved))
        call_start = time.monotonic()
        try:
            result = test_response(request, labels[request['question_id']], profile) if synthetic else ask_model(request, min(remaining, 120))
        except Exception as error:
            result = dict(status='error', text=None, error=type(error).__name__)
        append_row(folder/'responses.jsonl', dict(base, **result, elapsed_seconds=time.monotonic()-call_start))
        added += 1
        attempt_count += 1
        reserved_tokens += reserved
    summary = dict(added=added, stop_reason=stop_reason, synthetic=synthetic,
                   note='Failures and interrupted attempts are retained and not retried automatically.')
    append_row(folder/'execution.jsonl', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description='Prepare and check the Freeway representation experiment.')
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--config', type=Path, default=ROOT/'configs/stage_a.json')
    prepare_parser.add_argument('--output', type=Path, required=True)
    for name in ('preview', 'simulate', 'import', 'run'):
        command = commands.add_parser(name)
        command.add_argument('--run', type=Path, required=True)
        if name in ('simulate', 'run'):
            command.add_argument('--limit', type=int)
        if name == 'simulate':
            command.add_argument('--profile', choices=('perfect', 'wrong', 'malformed', 'mixed'), default='mixed')
        if name == 'import':
            command.add_argument('--file', type=Path, required=True)
        if name == 'preview':
            command.add_argument('--id', help='Situation ID; defaults to first selected scene')
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.config, args.output)
        print(json.dumps({key: result[key] for key in ('request_count', 'category_counts', 'selected_ids')}, indent=2))
    elif args.command == 'preview':
        manifest, _ = load_run(args.run)
        states = read_rows(args.run/'states.jsonl')
        state = next(s for s in states if args.id is None or s['situation_id'] == args.id)
        for name in manifest['settings']['formats']:
            print(f'=== {name} ===\n{render_scene(state["scene"], name)}')
    elif args.command == 'import':
        print(f'Imported {import_responses(args.run, args.file)} response records')
    else:
        print(json.dumps(execute(args.run, getattr(args, 'profile', None), args.limit), indent=2))


if __name__ == '__main__':
    main()
