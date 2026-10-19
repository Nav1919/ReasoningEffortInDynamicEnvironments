"""Build, query, run, or summarize reproducible Freeway pilot experiments.

Usage: python freeway_study.py --help; README.md distinguishes offline commands
from model calls. Inputs: simulator, CLI settings, or saved records. Outputs:
JSON/CSV evidence in --output. Checks: test_freeway_study.py and
 test_reproducibility.py. Diagnostic references never guide the live runner.
"""
# Two local experiments: fixed situations and matched live episode clocks.
# Diagnostic reference actions stay in this file. The live runner never imports
# them, so none of these simulations can select an action in a model episode.
import argparse
import copy
import csv
import hashlib
import gzip
import inspect
import itertools
import json
import random
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.request import urlopen

import realtimegym
from run_model_freeway import build_request, convert_scalar, parse_action, post_json, request_action

ROOT = Path(__file__).resolve().parent
MODEL = 'qwen3:4b-q4_K_M'
CONFIGS = [('original', 'full'), ('progress', 'full'), ('progress', 'structured')]
CATEGORIES = ['safe_forward', 'dangerous_forward', 'waiting_useful']


def write_json(path, value):
    # Replace our own checkpoint atomically, so an interrupted write leaves the
    # previous checkpoint readable. New runs always use a new results directory.
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, default=convert_scalar) + '\n')
    temporary.replace(path)


def internal_state(env):
    # __dict__ holds position, cars (including hidden timers), score, seed,
    # terminal/reset flags and lane choices. Include the whole RNG state too.
    # We save readable data, rather than an unsafe pickle requiring deserialization.
    def plain(value):
        if hasattr(value, 'tolist'):
            return value.tolist()
        if isinstance(value, (tuple, list)):
            return [plain(x) for x in value]
        if isinstance(value, dict):
            return {key: plain(item) for key, item in value.items()}
        return value
    state = {key: plain(value) for key, value in vars(env).items() if key != 'random'}
    state['random_state'] = plain(env.random.get_state())
    return state


def dynamics_key(env):
    # Ignore the printed turn and score when deduplicating. Repeated appearances
    # of the same traffic timers/cells and player position are cosmetic repeats.
    return json.dumps([env.pos, env.cars], default=convert_scalar, sort_keys=True)


def recreate(seed, prefix):
    env, actual_seed, _ = realtimegym.make('Freeway-v0', seed=seed, render=False)
    env.reset()
    for action in prefix:
        _, done, _, _ = env.step(action)
        if done:
            raise ValueError('A diagnostic prefix must end before termination')
    return env, int(actual_seed)


def simulate(env, actions):
    # deepcopy copies every field, including NumPy's random generator. Each
    # candidate action therefore starts from identical timers and random state.
    before = internal_state(env)
    trial = copy.deepcopy(env)
    initial_y = 9 - trial.pos
    trajectory = []
    for action in actions:
        if trial.terminal:
            break
        starting = copy.deepcopy(trial.observe())
        old_y = 9 - trial.pos
        observation, done, score, collision = trial.step(action)
        success = bool(done and action == 'U' and old_y == 8)
        # Winning resets internal pos and gives an empty observation. Count y=9
        # only from the verified goal transition, not from a positive reward.
        new_y = 9 if success else 9 - trial.pos
        trajectory.append(dict(action=action, observation_before=starting,
            observation_after=observation, collision=bool(collision),
            y_before=old_y, y_after=new_y, position_change=new_y-old_y,
            termination=bool(done), success=success, score=float(score)))
    assert internal_state(env) == before, 'Simulation changed its source state'
    return dict(actions=actions, horizon=len(actions), steps=trajectory,
                collision=any(s['collision'] for s in trajectory),
                final_y=trajectory[-1]['y_after'],
                position_change=trajectory[-1]['y_after']-initial_y,
                termination=trajectory[-1]['termination'],
                score=trajectory[-1]['score'])


def build_situations():
    # Generate candidates without looking at any model response. Fixed random
    # action tapes provide reachable positions/traffic, not manually edited cars.
    # The tapes are diagnostic construction only, never a live control policy.
    situations = []
    used = set()
    for seed in range(5):
        candidates = []
        local_seen = set()
        for tape in range(8):
            env, actual = recreate(seed, '')
            rng = random.Random(9100 + 100*seed + tape)
            prefix = ''
            for _ in range(55):
                if env.terminal:
                    break
                key = dynamics_key(env)
                y = 9 - env.pos
                if key not in local_seen and 0 <= y <= 7:
                    local_seen.add(key)
                    outcomes = {a: simulate(env, a) for a in 'UDS'}
                    waits = []
                    if outcomes['U']['collision']:
                        for count in range(1, 4):
                            outcome = simulate(env, 'S'*count + 'U')
                            if not outcome['collision'] and outcome['position_change'] > 0:
                                waits.append(outcome)
                    candidates.append(dict(env=copy.deepcopy(env), key=key,
                        prefix=prefix, y=y, outcomes=outcomes, waits=waits))
                action = rng.choices(['U', 'S', 'D'], weights=[6, 3, 1])[0]
                env.step(action)
                prefix += action
        for category in CATEGORIES:
            def qualifies(candidate):
                outcomes = candidate['outcomes']
                if category == 'safe_forward':
                    return not outcomes['U']['collision'] and outcomes['U']['position_change'] > 0
                if category == 'dangerous_forward':
                    return outcomes['U']['collision'] and any(not outcomes[a]['collision'] for a in 'DS')
                return bool(candidate['waits'])
            # Spread chosen player positions across the road. The remaining
            # tie-breaks use only replayable state properties, never model output.
            target_y = 1 + seed
            choices = [c for c in candidates if c['key'] not in used and qualifies(c)]
            if not choices:
                raise RuntimeError(f'No distinct {category} situation for seed {seed}')
            candidate = min(choices, key=lambda c: (abs(c['y']-target_y), len(c['prefix']), c['prefix']))
            used.add(candidate['key'])
            env = candidate['env']
            safe = [a for a in 'UDS' if not candidate['outcomes'][a]['collision']]
            item = dict(id=f'{category}_seed{seed}', category=category,
                synthetic=False, requested_seed=seed, actual_seed=actual,
                preceding_actions=candidate['prefix'], turn=int(env.game_turn),
                observation=copy.deepcopy(env.observe()), internal_state=internal_state(env),
                immediate=candidate['outcomes'], one_step_safe_actions=safe,
                acceptable_actions=['U'] if category == 'safe_forward' else safe,
                acceptable_criterion=('advance safely on the next step' if category == 'safe_forward'
                    else 'avoid collision on the next step; no claim of unique best action'))
            if category == 'waiting_useful':
                sequence = candidate['waits'][0]
                horizon = sequence['horizon']
                # At this same bounded horizon, examine all short alternatives.
                # Save all results so S is not declared uniquely correct when D
                # can also avoid a collision and make equal or better progress.
                alternatives = [simulate(env, ''.join(actions))
                    for actions in itertools.product('UDS', repeat=horizon)]
                successful = [s for s in alternatives if not s['collision'] and s['position_change'] > 0]
                item['waiting_reference'] = sequence
                item['same_horizon_alternatives'] = alternatives
                item['safe_progress_first_actions_at_horizon'] = sorted({s['actions'][0] for s in successful})
                item['waiting_criterion'] = 'S repeated 1–3 times then U gives collision-free forward progress; immediate U collides'
            # Recreate independently before accepting the saved situation.
            replayed, replay_seed = recreate(seed, item['preceding_actions'])
            assert replay_seed == actual and internal_state(replayed) == item['internal_state']
            situations.append(item)
    assert len(situations) == len(used) == 15
    return situations


def capture_metadata(folder):
    # Read only local endpoints. Record the exact installed digest rather than
    # assuming a mutable model tag means the same weights on every machine.
    metadata = {'recorded_utc': datetime.now(timezone.utc).isoformat()}
    for endpoint in ['version', 'tags']:
        with urlopen('http://localhost:11434/api/'+endpoint, timeout=30) as response:
            metadata[endpoint] = json.load(response)
    metadata['show'] = post_json('show', {'model': MODEL})
    metadata['installed_model'] = next(m for m in metadata['tags']['models'] if m['name'] == MODEL)
    env, _, _ = realtimegym.make('Freeway-v0', seed=0, render=False)
    source = Path(inspect.getfile(type(env)))
    metadata['environment_source'] = str(source)
    metadata['environment_source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    metadata['seed_mapping'] = {str(s): recreate(s, '')[1] for s in range(5)}
    metadata['difficulty'] = 'Freeway-v0 (E); unchanged'
    write_json(folder/'metadata.json', metadata)
    # Copy the audited source for durable provenance, not for execution.
    (folder/'environment_source.py.txt').write_bytes(source.read_bytes())


def record_request(payload):
    response, error, start, end = request_action(payload, None)
    parsed = parse_action(response, error)
    return dict(request=payload, response=response, error=error,
        parsed_action=parsed, valid_response=parsed is not None,
        fallback_action=None, executed_action=None,
        completion_reason=(response or {}).get('done_reason'),
        input_tokens=(response or {}).get('prompt_eval_count'),
        output_tokens=(response or {}).get('eval_count'),
        latency_seconds=end-start)


def run_diagnostics(folder):
    cases = build_situations()
    write_json(folder/'situations.json', cases)
    raw = folder/'diagnostics.jsonl'
    if raw.exists():
        raise FileExistsError('Choose a new results folder; never overwrite prior trials')
    args = SimpleNamespace(model=MODEL, tick_seconds=1.0, thinking='off',
                           prompt='original', board='full', model_seed=0)
    warmup = record_request(build_request(cases[0]['observation'], args))
    write_json(folder/'diagnostic_warmup.json', warmup)
    # Rotate prompt order and share seeds 0,1,2 for every situation. Each query
    # is stateless and sequential, and the saved game state never advances.
    count = 0
    with raw.open('x') as output:
        for index, case in enumerate(cases):
            env, _ = recreate(case['requested_seed'], case['preceding_actions'])
            before = internal_state(env)
            order = CONFIGS[index % 3:] + CONFIGS[:index % 3]
            for sampling_seed in [0, 1, 2]:
                for prompt, board in order:
                    args.prompt, args.board, args.model_seed = prompt, board, sampling_seed
                    entry = dict(situation_id=case['id'], category=case['category'],
                        prompt=prompt, board=board, model_seed=sampling_seed,
                        order=count, state_fixed_during_request=True,
                        started_utc=datetime.now(timezone.utc).isoformat())
                    # Write intent first so a process interruption still leaves
                    # the exact request that was attempted, even without a reply.
                    payload = build_request(case['observation'], args)
                    write_json(folder/'diagnostic_pending.json', dict(entry, request=payload))
                    entry.update(record_request(payload))
                    parsed = entry['parsed_action']
                    entry['reference_outcome'] = case['immediate'][parsed] if parsed else None
                    assert internal_state(env) == before
                    output.write(json.dumps(entry, default=convert_scalar)+'\n')
                    output.flush()
                    write_json(folder/'diagnostic_pending.json', {'completed_order': count})
                    count += 1
                    print(f'Diagnostic {count}/135: {case["id"]} {prompt}/{board} seed={sampling_seed} action={parsed}', flush=True)
    summarize(folder)


def live_order():
    # Five seeds cannot perfectly balance three order positions. These five
    # permutations put each interval in each position either once or twice.
    orders = [(1, 2, 4), (2, 4, 1), (4, 1, 2), (1, 4, 2), (2, 1, 4)]
    return [(seed, interval) for seed, order in enumerate(orders) for interval in order]


def run_live(folder):
    manifest_path = folder/'live_manifest.json'
    if manifest_path.exists():
        raise FileExistsError('Live manifest exists; preserve it and choose a new output folder')
    manifest = {'plan': live_order(), 'episodes': [], 'interruptions': [],
                'model_seed': 0, 'status': 'running'}
    write_json(manifest_path, manifest)
    try:
        for index, (seed, interval) in enumerate(live_order()):
            log = folder/f'live_{index:02d}_seed{seed}_tick{interval}.json'
            console = log.with_suffix('.txt')
            command = [sys.executable, str(ROOT/'run_model_freeway.py'),
                '--prompt', 'progress', '--board', 'full', '--thinking', 'off',
                '--seed', str(seed), '--model-seed', '0', '--tick-seconds', str(interval),
                '--model', MODEL, '--log-path', str(log)]
            entry = dict(order=index, requested_seed=seed, tick_seconds=interval,
                command=command, log=str(log), console=str(console),
                started_utc=datetime.now(timezone.utc).isoformat(), status='running')
            manifest['episodes'].append(entry)
            write_json(manifest_path, manifest)
            print(f'Live {index+1}/15: environment seed {seed}, {interval} seconds per turn', flush=True)
            # A subprocess uses the same runner/schedule for every episode.
            # Waiting for completion also waits for any late HTTP response, so
            # it cannot contend with the following episode's warm-up request.
            with console.open('x') as output:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
            entry['returncode'] = result.returncode
            entry['finished_utc'] = datetime.now(timezone.utc).isoformat()
            if result.returncode != 0:
                entry['status'] = 'failed'
                raise RuntimeError(f'Runner failed; inspect {console}')
            episode = json.loads(log.read_text())
            if not episode['summary']['episode_ended']:
                entry['status'] = 'incomplete'
                raise RuntimeError('Live episode did not reach environment termination')
            entry['status'] = 'complete'
            write_json(manifest_path, manifest)
            summarize(folder)
            print('Finished:', episode['summary'], flush=True)
        manifest['status'] = 'complete'
    except BaseException as error:
        manifest['status'] = 'interrupted_or_failed'
        manifest['interruptions'].append(dict(time=datetime.now(timezone.utc).isoformat(), error=repr(error)))
        raise
    finally:
        write_json(manifest_path, manifest)


def quantile(values, fraction):
    # Linear interpolation matches NumPy's default percentile convention.
    values = sorted(values)
    if not values:
        return None
    index = (len(values)-1)*fraction
    low = int(index)
    high = min(low+1, len(values)-1)
    return values[low] + (values[high]-values[low])*(index-low)


def latency_summary(values):
    return {'median': quantile(values, .5), 'p90': quantile(values, .9)}


def episode_metrics(episode):
    ds, steps = episode['decisions'], episode['steps']
    completed = [d for d in ds if 'response' in d]
    valid = [d for d in completed if d['valid_action']]
    applied = [d for d in completed if d.get('status') == 'applied']
    model_applied = [d for d in applied if d['valid_action']]
    last = steps[-1] if steps else None
    success = bool(last and last['done'] and last['action'] == 'U'
                   and last['observation_before']['state']['player_states'] == 8)
    assert success == episode['summary']['success']
    # Include before-states and the empty terminal goal observation correctly.
    positions = [int(episode['initial_observation']['state']['player_states'])]
    for s in steps:
        positions.extend(int(o['state']['player_states']) for o in
            [s['observation_before'], s['observation_after']] if 'state' in o)
    if success:
        positions.append(9)
    for s in steps:
        if s['action_source'] == 'model':
            d = ds[s['decision_id']]
            assert d['valid_action'] and d['parsed_action'] == s['action']
        elif s['action_source'] in ['waiting_default', 'invalid_fallback']:
            assert s['action'] == 'S'
    # Re-simulate model actions immediately at their saved observation. These
    # are retrospective labels ONLY, never inputs to the live controller.
    # Count choices already unsafe when seen versus collisions after delay.
    requested = episode['requested_seed']
    original, _ = recreate(requested, '')
    snapshots = {0: copy.deepcopy(original)}
    for step in steps:
        original.step(step['action'])
        snapshots[step['turn']] = copy.deepcopy(original)
    immediate_unsafe = sum(simulate(snapshots[d['observed_turn']], d['parsed_action'])['collision']
                           for d in model_applied)
    return dict(requested_seed=requested, actual_seed=episode['real_seed'],
        model_seed=episode['settings']['model_seed'], tick_seconds=episode['settings']['tick_seconds'],
        success=success, turns=episode['summary']['turns'],
        elapsed_seconds=episode['summary']['elapsed_seconds'], maximum_position=max(positions),
        collisions=episode['summary']['collisions'], final_score=episode['summary']['final_score'],
        responses=len(completed), valid=len(valid), invalid=len(completed)-len(valid),
        applied_responses=len(applied), applied_model_actions=len(model_applied),
        applied_fallbacks=len(applied)-len(model_applied),
        late_discarded=sum(d.get('status') == 'discarded_after_episode' for d in completed),
        raw_action_distribution={a:sum(d['parsed_action']==a for d in valid) for a in 'UDS'},
        executed_model_distribution={a:sum(d['parsed_action']==a for d in model_applied) for a in 'UDS'},
        latency=latency_summary([d['latency_seconds'] for d in completed]),
        observation_age_turns=latency_summary([d['observation_age_turns'] for d in applied]),
        observation_age_seconds=latency_summary([d['observation_age_seconds'] for d in applied]),
        ticks_during_requests=sum(d['ticks_during_request'] for d in completed),
        waiting_steps=sum(s['action_source']=='waiting_default' for s in steps),
        model_steps=sum(s['action_source']=='model' for s in steps),
        waiting_collisions=sum(s['collision'] and s['action_source']=='waiting_default' for s in steps),
        model_step_collisions=sum(s['collision'] and s['action_source']=='model' for s in steps),
        choices_unsafe_at_observation=immediate_unsafe,
        scheduler_lag=latency_summary([s['scheduler_lag_seconds'] for s in steps]),
        maximum_scheduler_lag=max([s['scheduler_lag_seconds'] for s in steps], default=0))


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v) if isinstance(v, (dict,list)) else v for k,v in row.items()})


def read_episode(path):
    """Read a plain or compressed saved episode; never calls the model."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        return json.load(stream)


def summarize(folder):
    # Rebuilding summaries never edits raw requests, observations or responses.
    diagnostic_path = folder/'diagnostics.jsonl'
    if diagnostic_path.exists():
        records = [json.loads(line) for line in diagnostic_path.read_text().splitlines()]
        rows = []
        for prompt, board in CONFIGS:
            for category in CATEGORIES + ['all']:
                trials = [r for r in records if r['prompt']==prompt and r['board']==board
                          and (category=='all' or r['category']==category)]
                if not trials:
                    continue
                valid = [r for r in trials if r['valid_response']]
                actions = Counter(r['parsed_action'] for r in valid)
                rows.append(dict(prompt=prompt, board=board, category=category, requests=len(trials),
                    valid=len(valid), invalid=len(trials)-len(valid),
                    valid_fraction=len(valid)/len(trials),
                    immediate_collisions=sum(r['reference_outcome']['collision'] for r in valid),
                    immediate_collision_fraction_among_valid=(sum(r['reference_outcome']['collision'] for r in valid)/len(valid) if valid else None),
                    safe_progress_choices=(actions['U'] if category=='safe_forward' else None),
                    avoided_U=(actions['D']+actions['S'] if category in ['dangerous_forward','waiting_useful'] else None),
                    waiting_choices=(actions['S'] if category=='waiting_useful' else None),
                    U=actions['U'], D=actions['D'], S=actions['S'],
                    latency_median=quantile([r['latency_seconds'] for r in trials],.5),
                    latency_p90=quantile([r['latency_seconds'] for r in trials],.9)))
        write_json(folder/'diagnostic_summary.json', rows)
        write_csv(folder/'diagnostic_summary.csv', rows)
    manifest_path = folder/'live_manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        rows, all_decisions = [], {}
        for entry in manifest['episodes']:
            if entry['status'] != 'complete':
                print(f"Excluded from metrics, retained in manifest: {entry['log']} ({entry['status']})", file=sys.stderr)
                continue
            # Prefer the packaged sibling log, even if an old machine path exists.
            log = folder / Path(entry['log']).name
            if not log.exists():
                log = Path(entry['log'])
            episode = read_episode(log)
            row = episode_metrics(episode)
            row['order'], row['log'] = entry['order'], entry['log']
            rows.append(row)
            all_decisions.setdefault(row['tick_seconds'], []).extend(episode['decisions'])
        write_json(folder/'live_episodes.json', rows)
        write_csv(folder/'live_episodes.csv', rows)
        aggregate = []
        for interval in [1,2,4]:
            group = [r for r in rows if r['tick_seconds']==interval]
            if not group:
                continue
            ds = all_decisions[interval]
            applied = [d for d in ds if d.get('status')=='applied']
            aggregate.append(dict(tick_seconds=interval, episodes=len(group),
                successes=sum(r['success'] for r in group),
                mean_maximum_position=statistics.mean(r['maximum_position'] for r in group),
                mean_collisions=statistics.mean(r['collisions'] for r in group),
                total_collisions=sum(r['collisions'] for r in group),
                total_turns=sum(r['turns'] for r in group),
                total_seconds=sum(r['elapsed_seconds'] for r in group),
                valid=sum(r['valid'] for r in group), invalid=sum(r['invalid'] for r in group),
                waiting_steps=sum(r['waiting_steps'] for r in group),
                model_steps=sum(r['model_steps'] for r in group),
                latency=latency_summary([d['latency_seconds'] for d in ds]),
                observation_age_turns=latency_summary([d['observation_age_turns'] for d in applied]),
                observation_age_seconds=latency_summary([d['observation_age_seconds'] for d in applied])))
        write_json(folder/'live_by_interval.json', aggregate)
        write_csv(folder/'live_by_interval.csv', aggregate)
        # A wide per-seed table makes the matched comparison explicit.
        paired = []
        for seed in range(5):
            row = {'requested_seed':seed, 'actual_seed':recreate(seed,'')[1]}
            for interval in [1,2,4]:
                found = next((r for r in rows if r['requested_seed']==seed and r['tick_seconds']==interval),None)
                for key in ['success','maximum_position','collisions','turns','waiting_steps','applied_model_actions']:
                    row[f'{interval}s_{key}'] = found[key] if found else None
            paired.append(row)
        write_json(folder/'live_paired.json', paired)
        write_csv(folder/'live_paired.csv', paired)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['build','smoke','diagnostics','live','all','summarize','plan','execute'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--limit', type=int, default=1)
    parser.add_argument('--attempt', type=int, default=1)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if args.mode == 'execute':
        from comparison_execution import execute_plan
        if args.dry_run:
            parser.error('Use plan --dry-run before execution')
        execute_plan(folder, args.limit)
        return
    if args.mode == 'plan':
        from comparison_plan import build_plan
        from experiment_config import load_config
        if not args.config:
            parser.error('plan requires --config')
        plan = build_plan(load_config(args.config), args.attempt)
        path = folder/'plan.json'
        with path.open('x') as stream:
            json.dump(plan, stream, indent=2, default=convert_scalar)
        print(f"Saved {len(plan['runs'])} planned runs to {path}; no model calls")
        return
    if args.dry_run:
        parser.error('--dry-run is supported only with plan')
    if args.mode == 'build':
        write_json(folder/'situations.json', build_situations())
        return
    if args.mode == 'summarize':
        if (folder/'plan.json').exists():
            from comparison_metrics import write_comparison_summary
            write_comparison_summary(folder)
        else:
            summarize(folder)
        return
    if not (folder/'metadata.json').exists():
        capture_metadata(folder)
    if args.mode == 'smoke':
        path = folder/'smoke.json'
        if path.exists():
            raise FileExistsError('Smoke record exists; choose a new output folder')
        env, actual_seed = recreate(0, '')
        settings = SimpleNamespace(model=MODEL, prompt='progress', board='full',
            thinking='off', tick_seconds=1.0, model_seed=0)
        record = record_request(build_request(env.observe(), settings))
        record.update(requested_seed=0, actual_seed=actual_seed, observation=env.observe(),
                      note='Single frozen-state request; no action executed')
        write_json(path, record)
        print(f"Saved {path}; valid response: {record['valid_response']}")
        if not record['valid_response']:
            raise RuntimeError('Smoke response invalid; inspect saved record')
        return
    if args.mode in ['diagnostics','all']:
        run_diagnostics(folder)
    if args.mode in ['live','all']:
        run_live(folder)


if __name__ == '__main__':
    main()
