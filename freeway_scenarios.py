"""Save and replay Freeway scenarios for later experiments.

Run `python freeway_scenarios.py generate`, `run --id 42`, or `summary`.
The installed simulator supplies states and answers; one local JSON file stores
them. No model calls. Checks: test_freeway_scenarios.py.
"""
import argparse
import copy
import hashlib
import inspect
import json
import random
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np

from freeway_study import dynamics_key, internal_state, recreate, simulate

DEFAULT_FILE = Path(__file__).resolve().parent / 'data/freeway_scenarios.json'
ACTIONS = 'UDS'
CATEGORIES = ('safe_advance', 'waiting_helps', 'must_retreat', 'dangerous_advance')
CATEGORY_NAMES = dict(zip(CATEGORIES, ('Safe advance', 'Waiting helps',
                                      'Must retreat', 'Other dangerous advances')))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def plain(value):
    if hasattr(value, 'tolist'):
        return plain(value.tolist())
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True).encode()).hexdigest()


def restore(record):
    # Keep array types and random state intact when restoring JSON.
    env, actual = recreate(record['requested_seed'], '')
    if actual != record['actual_seed']:
        raise ValueError('Actual seed changed')
    snapshot = record['snapshot']
    for name, value in snapshot.items():
        if name != 'random_state':
            previous = getattr(env, name, None)
            setattr(env, name, np.array(value, dtype=previous.dtype)
                    if isinstance(previous, np.ndarray) else copy.deepcopy(value))
    rng = snapshot['random_state']
    env.random.set_state((rng[0], np.array(rng[1], dtype=np.uint32),
                          rng[2], rng[3], rng[4]))
    return env


def answer_key(env, horizon=10, cache=None):
    if not 1 <= horizon <= 10 or env.terminal:
        raise ValueError('Require nonterminal state and horizon 1..10')
    before = digest(internal_state(env))
    cache = {} if cache is None else cache
    initial_cache_size = len(cache)

    # Stop at collisions, even when the game resets afterward.
    # Reuse results only when the full state and remaining time match.
    def options(state, remaining):
        key = (digest(internal_state(state)), remaining)
        if key in cache:
            return cache[key]
        result = {}
        for action in ACTIONS:
            trial = copy.deepcopy(state)
            old_y = 9 - trial.pos
            _, done, _, collision = trial.step(action)
            goal = bool(done and action == 'U' and old_y == 8)
            if collision:
                result[action] = None
                continue
            if goal:
                value = dict(goal=True, goal_ticks=1, final_y=9, witness=action)
            elif done:
                result[action] = None
                continue
            elif remaining == 1:
                value = dict(goal=False, goal_ticks=None, final_y=9-trial.pos,
                             witness=action)
            else:
                children = [v for v in options(trial, remaining-1).values() if v]
                if not children:
                    result[action] = None
                    continue
                child = max(children, key=rank)
                value = dict(child, witness=action+child['witness'],
                             goal_ticks=child['goal_ticks']+1 if child['goal'] else None)
            result[action] = value
        cache[key] = result
        return result

    immediate = {a: simulate(env, a) for a in ACTIONS}
    horizons = {}
    for depth in range(1, horizon+1):
        outcomes = options(env, depth)
        valid = [v for v in outcomes.values() if v]
        best_rank = max(map(rank, valid)) if valid else None
        horizons[str(depth)] = dict(
            safe_first_actions=[a for a, v in outcomes.items() if v],
            best_first_actions=[a for a, v in outcomes.items()
                                if v and rank(v) == best_rank],
            outcomes=outcomes)
    safe = horizons[str(horizon)]['safe_first_actions']
    waiting = []
    if immediate['U']['collision']:
        for n in range(1, min(3, horizon-1)+1):
            result = simulate(env, 'S'*n+'U')
            if not result['collision'] and result['position_change'] > 0:
                waiting.append(result['actions'])
    if safe == ['D']:
        category = 'must_retreat'
    elif waiting:
        category = 'waiting_helps'
    elif 'U' in safe and immediate['U']['position_change'] > 0:
        category = 'safe_advance'
    elif immediate['U']['collision'] and safe:
        category = 'dangerous_advance'
    else:
        category = 'other'
    assert before == digest(internal_state(env)), 'Labeling mutated source'
    return dict(horizon=horizon, category=category, immediate=immediate,
                waiting_witnesses=waiting, by_horizon=horizons,
                search_states=len(cache)-initial_cache_size, source_unchanged=True)


def rank(value):
    # Prefer a faster crossing; otherwise compare final progress. Keep ties.
    return (int(value['goal']), -value['goal_ticks'] if value['goal'] else value['final_y'])



def simulator_hash():
    env, _ = recreate(0, '')
    return hashlib.sha256(Path(inspect.getfile(type(env))).read_bytes()).hexdigest()


def generate(path=DEFAULT_FILE, count=500, selectors=5, ticks=89, seed=473, horizon=10):
    require(count > 0 and 1 <= selectors <= 5 and 1 <= ticks <= 89,
            'Use a positive count, 1–5 development starts, and 1–89 ticks.')
    require(1 <= horizon <= 10, 'Horizon must be 1–10.')
    require(not path.exists(), f'{path} already exists; choose another --file.')
    pools, seen, cache = defaultdict(list), set(), {}
    for selector in range(selectors):
        env, actual = recreate(selector, '')
        queue, local_seen = deque([(env, '')]), {dynamics_key(env)}
        while queue:
            env, prefix = queue.popleft()
            physical_state = dynamics_key(env)
            if physical_state not in seen:
                seen.add(physical_state)
                snapshot = plain(internal_state(env))
                answer = answer_key(env, horizon, cache)
                pools[answer['category']].append(dict(
                    requested_seed=selector, actual_seed=actual,
                    preceding_actions=prefix, snapshot=snapshot,
                    state_sha256=digest(snapshot), dynamics_sha256=digest(physical_state),
                    observation=plain(env.observe()), category=answer['category'], answer=answer))
            if len(prefix) >= ticks:
                continue
            for action in ACTIONS:
                trial = copy.deepcopy(env)
                _, done, _, collision = trial.step(action)
                if done or collision:
                    continue
                key = dynamics_key(trial)
                if key not in local_seen:
                    local_seen.add(key)
                    queue.append((trial, prefix+action))
        print(f'Explored start {selector+1}/{selectors}: {len(local_seen)} situations', flush=True)

    # Take the earliest visit to each situation, then spread choices across
    # categories, player lanes, and starts. Rare categories are not invented.
    available = {c: len(pools[c]) for c in (*CATEGORIES, 'other')}
    require(sum(available[c] for c in CATEGORIES) >= count,
            f'Not enough eligible situations for {count} scenarios: {available}')
    rng = random.Random(seed)
    for records in pools.values():
        rng.shuffle(records)
    scenarios, chosen, lanes, starts = [], Counter(), Counter(), Counter()
    while len(scenarios) < count:
        category = min((c for c in CATEGORIES if pools[c]),
                       key=lambda c: (chosen[c], CATEGORIES.index(c)))
        records = pools[category]
        index = min(range(len(records)), key=lambda i: (
            lanes[records[i]['observation']['state']['player_states']],
            starts[records[i]['actual_seed']]))
        record = records.pop(index)
        record['id'] = len(scenarios)
        scenarios.append(record)
        chosen[category] += 1
        lanes[record['observation']['state']['player_states']] += 1
        starts[record['actual_seed']] += 1
    metadata = dict(schema_version=1, count=count, seed=seed, selectors=selectors,
        ticks=ticks, horizon=horizon, simulator_sha256=simulator_hash(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        available_categories=available, category_counts=dict(chosen),
        lane_counts=dict(sorted(lanes.items())), start_counts=dict(sorted(starts.items())),
        split='development_only')
    print(f'Checking {count} scenarios before saving...', flush=True)
    metadata['verification'] = verify_scenarios(scenarios)
    bank = dict(metadata=metadata, scenarios=scenarios, scenarios_sha256=digest(scenarios))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(plain(bank), stream, indent=2)
        stream.write('\n')
    print(f'Saved {count} scenarios to {path}')
    return bank


def load(path):
    bank = json.loads(path.read_text())
    require(digest(bank['scenarios']) == bank['scenarios_sha256'], 'Scenario file changed.')
    require(simulator_hash() == bank['metadata']['simulator_sha256'], 'Simulator source changed.')
    require(len(bank['scenarios']) == bank['metadata']['count'], 'Scenario count mismatch.')
    counts = dict(Counter(s['category'] for s in bank['scenarios']))
    require(counts == bank['metadata']['category_counts'], 'Category counts changed.')
    return bank


def verify_scenarios(scenarios):
    require(len({s['id'] for s in scenarios}) == len(scenarios), 'Duplicate scenario ID.')
    require(len({s['dynamics_sha256'] for s in scenarios}) == len(scenarios),
            'Repeated physical situation.')
    cache, witnesses = {}, 0
    for record in scenarios:
        env = restore(record)
        replayed, actual = recreate(record['requested_seed'], record['preceding_actions'])
        require(actual == record['actual_seed'], 'Starting seed changed.')
        require(digest(internal_state(env)) == digest(internal_state(replayed))
                == record['state_sha256'], 'Snapshot and replay disagree.')
        require(digest(dynamics_key(env)) == record['dynamics_sha256'], 'Physical state changed.')
        require(plain(env.observe()) == record['observation'], 'Observation changed.')
        expected = plain(record['answer'])
        actual_answer = plain(answer_key(env, expected['horizon'], cache))
        require(record['category'] == expected['category'], 'Scenario category mismatch.')
        require({k:v for k,v in actual_answer.items() if k != 'search_states'} ==
                {k:v for k,v in expected.items() if k != 'search_states'}, 'Answer key changed.')
        for depth, entry in expected['by_horizon'].items():
            for action, value in entry['outcomes'].items():
                if not value:
                    continue
                result = simulate(replayed, value['witness'])
                require(value['witness'][0] == action and not result['collision'],
                        'Saved sequence is not safe.')
                require(result['final_y'] == value['final_y'] and
                        result['steps'][-1]['success'] == value['goal'], 'Outcome changed.')
                require(len(result['steps']) == (value['goal_ticks'] if value['goal'] else int(depth))
                        and (value['goal'] or not result['termination']), 'Sequence ended early.')
                witnesses += 1
    return dict(scenarios_verified=len(scenarios), sequences_replayed=witnesses, passed=True)


def summary(bank):
    print(f"Total: {len(bank['scenarios'])} scenarios")
    for category in CATEGORIES:
        print(f"{CATEGORY_NAMES[category]}: "
              f"{bank['metadata']['category_counts'].get(category, 0)}")


def run(bank, scenario_id=None, category=None):
    scenarios = [s for s in bank['scenarios'] if
                 (scenario_id is None or s['id'] == scenario_id) and
                 (category is None or s['category'] == category)]
    require(bool(scenarios), 'No matching scenarios.')
    result = verify_scenarios(scenarios)
    if scenario_id is not None:
        record = scenarios[0]
        answer = record['answer']
        entry = answer['by_horizon'][str(answer['horizon'])]
        print(f"Scenario {record['id']} — {record['category'].replace('_', ' ')}")
        print(f"Player: lane {record['observation']['state']['player_states']}")
        for action, name in zip(ACTIONS, ('Up', 'Down', 'Stay')):
            status = 'collision' if answer['immediate'][action]['collision'] else 'no collision'
            print(f'{name}: {status} on the next tick')
        print(f"Best first moves over {answer['horizon']} ticks: {', '.join(entry['best_first_actions'])}")
        for action in entry['best_first_actions']:
            print(f"Example starting with {action}: {entry['outcomes'][action]['witness']}")
    print(f"Verified {result['scenarios_verified']} scenarios and "
          f"{result['sequences_replayed']} saved sequences.")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('generate', help='Generate scenarios and answer keys.')
    create.add_argument('--count', type=int, default=500)
    create.add_argument('--seed', type=int, default=473)
    replay = commands.add_parser('run', help='Replay scenarios and check their answers.')
    choice = replay.add_mutually_exclusive_group(required=True)
    choice.add_argument('--id', type=int)
    choice.add_argument('--category', choices=CATEGORIES)
    choice.add_argument('--all', action='store_true')
    show = commands.add_parser('summary', help='Show category counts.')
    for command in (create, replay, show):
        command.add_argument('--file', type=Path, default=DEFAULT_FILE)
    args = parser.parse_args(argv)
    try:
        if args.command == 'generate':
            summary(generate(args.file, count=args.count, seed=args.seed))
        elif args.command == 'summary':
            summary(load(args.file))
        else:
            run(load(args.file), args.id, args.category)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
