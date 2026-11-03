"""Collect reachable Freeway checkpoints and label bounded safe continuations.

Run: .venv/bin/python situation_bank.py collect --output PATH; then use label
and verify with the same --output. Inputs: installed simulator and seeded policies.
Outputs: JSON checkpoints, labels, provenance and validation reports. No model
calls. Tests: test_situation_bank.py; protocol: docs/situation_bank.md.
"""
import argparse
import copy
import hashlib
import inspect
import json
import platform
import random
from collections import Counter, defaultdict, deque
from pathlib import Path

import numpy as np

from freeway_study import dynamics_key, internal_state, recreate, simulate

ACTIONS = 'UDS'
POLICIES = {'forward': (6, 1, 3), 'random': (1, 1, 1), 'waiting': (2, 1, 7)}


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


def write(path, value):
    path.write_text(json.dumps(plain(value), indent=2) + '\n')


def restore(record):
    # Restore readable snapshots, preserving NumPy arrays and the entire RNG.
    # Replay from the seed and action prefix is checked independently in verify.
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


def collect(output, count=50, selectors=5, ticks=60, seed=473):
    if count < 1 or not 1 <= selectors <= 5 or not 1 <= ticks <= 90:
        raise ValueError('Positive count, 1..5 development selectors and ticks in 1..90 required')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be new or empty')
    candidates, seen = [], set()
    for selector in range(selectors):
        for policy_index, (policy, weights) in enumerate(POLICIES.items()):
            env, actual = recreate(selector, '')
            policy_seed = seed + selector * 100 + policy_index
            rng, prefix = random.Random(policy_seed), ''
            for _ in range(ticks):
                if env.terminal:
                    break
                key = dynamics_key(env)
                if key not in seen:
                    seen.add(key)
                    snapshot = plain(internal_state(env))
                    candidates.append(dict(requested_seed=selector, actual_seed=actual,
                        policy=policy, policy_seed=policy_seed, preceding_actions=prefix,
                        snapshot=snapshot, state_sha256=digest(snapshot),
                        dynamics_sha256=digest(key), observation=plain(env.observe())))
                action = rng.choices(ACTIONS, weights=weights)[0]
                env.step(action)
                prefix += action
    if len(candidates) < count:
        raise ValueError(f'Only {len(candidates)} distinct candidates; requested {count}')

    # Sample across actual initialization, player lane and collection policy.
    # This engineering pilot measures category availability, not preset quotas.
    random.Random(seed).shuffle(candidates)
    groups = defaultdict(list)
    for record in candidates:
        groups[(record['actual_seed'], record['observation']['state']['player_states'],
                record['policy'])].append(record)
    keys = sorted(groups)
    random.Random(seed).shuffle(keys)
    selected = []
    while len(selected) < count:
        for key in keys:
            if groups[key] and len(selected) < count:
                selected.append(groups[key].pop())
    for index, record in enumerate(selected):
        record['id'] = f'freeway_{index:04d}'
    env = restore(selected[0])
    source = Path(inspect.getfile(type(env)))
    output.mkdir(parents=True, exist_ok=True)
    write(output / 'states.json', selected)
    report = dict(schema_version=1, game='Freeway-v0', count=count,
        candidate_count=len(candidates), selectors=selectors, ticks=ticks, seed=seed,
        policies=POLICIES, python=platform.python_version(),
        environment_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        states_sha256=digest(selected), split='engineering_pilot_only',
        selected_actual_seeds=sorted({r['actual_seed'] for r in selected}),
        lane_counts=dict(Counter(str(r['observation']['state']['player_states'])
                                 for r in selected)),
        policy_counts=dict(Counter(r['policy'] for r in selected)))
    write(output / 'manifest.json', report)
    return report


def balanced_bank(output, count=500, selectors=5, ticks=89, seed=473, horizon=10):
    """Explore collision-free reachable states, then select by measured category."""
    if count < 1 or not 1 <= selectors <= 5 or not 1 <= ticks <= 89:
        raise ValueError('Require positive count, 1..5 development starts and ticks 1..89')
    if not 1 <= horizon <= 10:
        raise ValueError('Horizon must be 1..10')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output directory must be new or empty')
    candidates, seen = [], set()
    for selector in range(selectors):
        env, actual = recreate(selector, '')
        queue = deque([(env, '')])
        local_seen = {dynamics_key(env)}
        while queue:
            env, prefix = queue.popleft()
            key = dynamics_key(env)
            if key not in seen:
                seen.add(key)
                snapshot = plain(internal_state(env))
                candidates.append(dict(requested_seed=selector, actual_seed=actual,
                    policy='reachable_search', policy_seed=None,
                    preceding_actions=prefix, snapshot=snapshot,
                    state_sha256=digest(snapshot), dynamics_sha256=digest(key),
                    observation=plain(env.observe())))
            if len(prefix) >= ticks:
                continue
            for action in ACTIONS:
                trial = copy.deepcopy(env)
                _, done, _, collision = trial.step(action)
                if done or collision:
                    continue
                next_key = dynamics_key(trial)
                if next_key not in local_seen:
                    local_seen.add(next_key)
                    queue.append((trial, prefix+action))
        print(f'Explored start {selector}: {len(local_seen)} reachable physical states', flush=True)

    # The search keeps the earliest visit to a physical configuration, preventing
    # timeout variants from filling the bank. All candidates have real action
    # prefixes; no car, player, or clock values are edited to improve coverage.
    pools = defaultdict(list)
    cache = {}
    inventory = []
    for index, record in enumerate(candidates):
        key = answer_key(restore(record), horizon, cache)
        pools[key['category']].append(record)
        inventory.append(dict(state_sha256=record['state_sha256'],
            dynamics_sha256=record['dynamics_sha256'], category=key['category'],
            actual_seed=record['actual_seed'],
            player_lane=record['observation']['state']['player_states']))
        if (index+1) % 100 == 0:
            print(f'Classified {index+1}/{len(candidates)} candidates', flush=True)
    categories = ['safe_advance', 'waiting_helps', 'must_retreat', 'dangerous_advance']
    available = {c:len(pools[c]) for c in categories+['other']}
    if sum(available[c] for c in categories) < count:
        raise ValueError(f'Insufficient eligible states: {available}; requested {count}')
    rng = random.Random(seed)
    for records in pools.values():
        rng.shuffle(records)
    selected, chosen = [], Counter()
    lane_counts, start_counts = Counter(), Counter()
    requested = {c:count//4 + int(i < count % 4) for i,c in enumerate(categories)}
    while len(selected) < count:
        remaining = [c for c in categories if pools[c]]
        category = min(remaining, key=lambda c:(chosen[c], categories.index(c)))
        records = pools[category]
        index = min(range(len(records)), key=lambda i:(
            lane_counts[records[i]['observation']['state']['player_states']],
            start_counts[records[i]['actual_seed']]))
        record = records.pop(index)
        record['id'] = f'freeway_{len(selected):04d}'
        selected.append(record)
        chosen[category] += 1
        lane_counts[record['observation']['state']['player_states']] += 1
        start_counts[record['actual_seed']] += 1
    env = restore(selected[0])
    source = Path(inspect.getfile(type(env)))
    output.mkdir(parents=True, exist_ok=True)
    write(output/'states.json', selected)
    manifest = dict(schema_version=2, game='Freeway-v0', count=count,
        candidate_count=len(candidates), selectors=selectors, ticks=ticks, seed=seed,
        collection='breadth_first_collision_free_reachability', horizon=horizon,
        selection='category_then_underrepresented_lane_and_start',
        split='development_only_no_held_out_claim', python=platform.python_version(),
        environment_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        generator_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        states_sha256=digest(selected), requested_category_counts=requested,
        available_category_counts=available, selected_category_counts=dict(chosen),
        category_shortfalls={c:max(0, requested[c]-available[c]) for c in categories},
        lane_counts=dict(sorted(lane_counts.items())),
        actual_seed_counts=dict(sorted(start_counts.items())),
        selected_actual_seeds=sorted(start_counts),
        excluded_other=available['other'])
    write(output/'manifest.json', manifest)
    write(output/'candidate_inventory.json', inventory)
    print(json.dumps(manifest, indent=2), flush=True)
    label(output, horizon)
    return verify(output)


def answer_key(env, horizon=10, cache=None):
    if not 1 <= horizon <= 10 or env.terminal:
        raise ValueError('Require nonterminal state and horizon 1..10')
    before = digest(internal_state(env))
    cache = {} if cache is None else cache
    initial_cache_size = len(cache)

    # Collision branches are rejected immediately, including reset transitions.
    # Memoization merges identical exact states, not just matching observations.
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
    # Goal first, then faster goal arrival; otherwise maximize final progress.
    # All equally ranked first actions are retained, even with different witnesses.
    return (int(value['goal']), -value['goal_ticks'] if value['goal'] else value['final_y'])


def load_bank(output):
    states = json.loads((output/'states.json').read_text())
    manifest = json.loads((output/'manifest.json').read_text())
    if digest(states) != manifest['states_sha256']:
        raise ValueError('Saved states checksum mismatch')
    source = Path(inspect.getfile(type(restore(states[0]))))
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['environment_source_sha256']:
        raise ValueError('Simulator source changed')
    return states


def label(output, horizon=10):
    states = load_bank(output)
    if (output/'labels.json').exists():
        raise ValueError('Labels already exist; use a new pilot directory')
    labels, cache = [], {}
    for index, record in enumerate(states):
        labels.append(dict(id=record['id'], state_sha256=record['state_sha256'],
                           **answer_key(restore(record), horizon, cache)))
        if (index+1) % 10 == 0:
            print(f'Labeled {index+1}/{len(states)} states', flush=True)
    write(output/'labels.json', labels)
    report = dict(count=len(labels), horizon=horizon, labels_sha256=digest(labels),
                  category_counts=dict(Counter(r['category'] for r in labels)),
                  search_states=sum(r['search_states'] for r in labels))
    write(output/'label_report.json', report)
    examples = []
    for category in ('safe_advance', 'waiting_helps', 'must_retreat', 'dangerous_advance', 'other'):
        pair = next(((s, k) for s, k in zip(states, labels) if k['category'] == category), None)
        if pair is None:
            continue
        state, key = pair
        entry = key['by_horizon'][str(horizon)]
        examples.append(dict(id=state['id'], category=category,
            player_lane=state['observation']['state']['player_states'],
            tick=state['snapshot']['game_turn'],
            immediate_collisions={a:r['collision'] for a,r in key['immediate'].items()},
            horizon=horizon, safe_first_actions=entry['safe_first_actions'],
            best_first_actions=entry['best_first_actions'],
            best_witnesses={a:entry['outcomes'][a] for a in entry['best_first_actions']},
            waiting_witnesses=key['waiting_witnesses']))
    write(output/'examples.json', examples)
    return report


def verify(output):
    states = load_bank(output)
    labels = json.loads((output/'labels.json').read_text())
    report = json.loads((output/'label_report.json').read_text())
    if digest(labels) != report['labels_sha256']:
        raise ValueError('Labels checksum mismatch')
    assert [s['id'] for s in states] == [r['id'] for r in labels]
    assert len({r['dynamics_sha256'] for r in states}) == len(states)
    witnesses = 0
    cache = {}
    for record, key in zip(states, labels):
        env = restore(record)
        replayed, actual = recreate(record['requested_seed'], record['preceding_actions'])
        assert actual == record['actual_seed']
        assert digest(internal_state(env)) == digest(internal_state(replayed)) == record['state_sha256']
        assert plain(env.observe()) == record['observation']
        assert key['state_sha256'] == record['state_sha256']
        recomputed = plain(answer_key(env, key['horizon'], cache))
        assert {k:v for k,v in recomputed.items() if k != 'search_states'} == {
            k:v for k,v in key.items() if k not in ('id', 'state_sha256', 'search_states')}
        for depth, entry in key['by_horizon'].items():
            for action, value in entry['outcomes'].items():
                if value:
                    result = simulate(replayed, value['witness'])
                    assert value['witness'][0] == action
                    assert not result['collision']
                    assert result['steps'][-1]['success'] == value['goal']
                    assert result['final_y'] == value['final_y']
                    assert (len(result['steps']) == value['goal_ticks'] if value['goal']
                            else not result['termination'] and len(result['steps']) == int(depth))
                    witnesses += 1
    result = dict(states_verified=len(states), witnesses_replayed=witnesses,
                  snapshot_and_prefix_agree=True, labels_recomputed=True,
                  duplicate_dynamics=0, passed=True)
    write(output/'validation_report.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect', 'balanced', 'label', 'verify'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=50)
    parser.add_argument('--selectors', type=int, default=5)
    parser.add_argument('--ticks', type=int, default=60)
    parser.add_argument('--seed', type=int, default=473)
    parser.add_argument('--horizon', type=int, default=10)
    args = parser.parse_args()
    if args.command == 'collect':
        result = collect(args.output, args.count, args.selectors, args.ticks, args.seed)
    elif args.command == 'balanced':
        result = balanced_bank(args.output, args.count, args.selectors, args.ticks,
                               args.seed, args.horizon)
    elif args.command == 'label':
        result = label(args.output, args.horizon)
    else:
        result = verify(args.output)
    print(json.dumps(result, indent=2))
