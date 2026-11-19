"""Read-only observation-age and traffic-change audit of saved Freeway episodes.

Usage: python freshness_audit.py EPISODE.json[.gz] [...]
Import audit_episode(dict) for native runner records. Inputs are saved decisions
and ticks, not simulator state or model calls; output is JSON with per-decision
metrics and explicit missingness. See docs/weekend/freshness-audit.md for the
proposed interface and limits. Tested by test_freshness_audit.py using
python -m unittest test_freshness_audit -v. Uses only the standard library.
"""
import argparse
from collections import Counter
import gzip
import json
import math
from pathlib import Path


# Missing data is distinct from invalid data: absent/null values stay unknown,
# but present malformed values and contradictory clocks must never become ages.
def number(record, key, integer=False):
    value = record.get(key)
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0
            or (integer and not isinstance(value, int))):
        raise ValueError(f'{key}: expected nonnegative finite {"integer" if integer else "number"}')
    return value


def consistent(actual, expected, label):
    if actual is not None and expected is not None and not math.isclose(
            actual, expected, rel_tol=0, abs_tol=1e-8):
        raise ValueError(f'{label}: inconsistent values')


def traffic(observation):
    """Canonical multiset of exposed car rows; no player/clock or hidden state."""
    if observation is None:
        return None
    if not isinstance(observation, dict):
        raise ValueError('observation must be an object')
    state = observation.get('state')
    if state is None:
        return None
    if not isinstance(state, dict):
        raise ValueError('state must be an object')
    cars = state.get('car_states')
    if cars is None:
        return None
    if not isinstance(cars, list):
        raise ValueError('car_states must be a list')
    rows = []
    for row in cars:
        if not isinstance(row, list) or len(row) != 5:
            raise ValueError('car row must be [lane, head, direction, speed, length]')
        lane, head, direction, speed, length = row
        if direction not in ('left', 'right'):
            raise ValueError('invalid car direction')
        for value in (lane, head, speed, length):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('car coordinates must be finite numbers')
        if lane < 0 or speed < 0 or length < 0:
            raise ValueError('negative lane, speed or length')
        rows.append(tuple(row))
    return Counter(rows)


# Join only explicit decision IDs to pre-action observations. Post-action and
# terminal observations are never substituted for a missing action-time view.
def audit_episode(episode):
    """Audit native run_model_freeway records without mutating or relabeling them."""
    decisions = episode.get('decisions', [])
    steps = episode.get('steps', [])
    if not isinstance(decisions, list) or not isinstance(steps, list):
        raise ValueError('decisions and steps must be lists')
    by_id = {}
    ended = False
    previous_turn = previous_time = None
    for step in steps:
        if ended:
            raise ValueError('step after terminal state')
        turn = number(step, 'turn', True)
        tick = number(step, 'elapsed_seconds')
        number(step, 'scheduler_lag_seconds')
        if turn == 0:
            raise ValueError('action tick turn must be positive')
        if turn is not None and previous_turn is not None and turn <= previous_turn:
            raise ValueError('tick turns must increase')
        if tick is not None and previous_time is not None and tick < previous_time:
            raise ValueError('tick timestamps must not decrease')
        if turn is not None:
            previous_turn = turn
        if tick is not None:
            previous_time = tick
        if 'done' in step and not isinstance(step['done'], bool):
            raise ValueError('done must be boolean')
        ended = step.get('done', False)
        identity = number(step, 'decision_id', True)
        if identity is not None:
            if identity in by_id:
                raise ValueError('decision applied more than once')
            by_id[identity] = step

    results = []
    seen = set()
    for decision in decisions:
        identity = number(decision, 'id', True)
        if identity is None or identity in seen:
            raise ValueError('decision IDs must be present and unique')
        seen.add(identity)
        step = by_id.get(identity)
        status = decision.get('status')
        if step is not None and status in ('discarded_after_episode', 'pending_when_episode_ended'):
            raise ValueError('discarded/pending decision has an action tick')
        times = {key: number(decision, key) for key in (
            'observed_seconds', 'submitted_seconds', 'request_started_seconds',
            'response_finished_seconds', 'applied_seconds')}
        ordered = [value for value in times.values() if value is not None]
        if ordered != sorted(ordered):
            raise ValueError('inconsistent observation/request/response/action timing')
        observed_turn = number(decision, 'observed_turn', True)
        applied_turn = number(decision, 'applied_turn', True)
        collected_turn = number(decision, 'response_collected_turn', True)
        number(decision, 'ticks_during_request', True)
        for key in ('latency_seconds', 'observation_age_seconds', 'observation_age_turns'):
            number(decision, key, key.endswith('turns'))
        supplied = decision.get('observation')
        supplied_traffic = traffic(supplied)
        if isinstance(supplied, dict):
            consistent(number(supplied, 'game_turn', True), observed_turn, 'supplied turn')
        if collected_turn is not None and observed_turn is not None and collected_turn < observed_turn:
            raise ValueError('response collected before supplied turn')
        if step is not None:
            tick = number(step, 'elapsed_seconds')
            turn = number(step, 'turn', True)
            consistent(times['applied_seconds'], tick, 'action timestamp')
            consistent(applied_turn, turn, 'action turn')
            times['applied_seconds'] = tick if tick is not None else times['applied_seconds']
            applied_turn = turn if turn is not None else applied_turn
            before = step.get('observation_before')
            if isinstance(before, dict) and applied_turn is not None:
                consistent(number(before, 'game_turn', True), applied_turn - 1, 'pre-action turn')
            action_traffic = traffic(before)
        else:
            action_traffic = None
        ordered = [value for value in times.values() if value is not None]
        if ordered != sorted(ordered):
            raise ValueError('action tick precedes observation/request/response')
        if applied_turn == 0:
            raise ValueError('applied_turn must be positive')
        if status in ('discarded_after_episode', 'pending_when_episode_ended') and (
                applied_turn is not None or times['applied_seconds'] is not None):
            raise ValueError('unapplied decision has application fields')
        # A supplied application timestamp/turn supports age even when its tick
        # record is absent. Traffic comparison still requires an explicit join.
        def difference(end, start):
            if end is None or start is None:
                return None
            if end < start:
                raise ValueError('negative duration or turn age')
            return end - start
        age_turns = difference(None if applied_turn is None else applied_turn - 1, observed_turn)
        if applied_turn is not None and collected_turn is not None and collected_turn >= applied_turn:
            raise ValueError('response collected after action turn')
        metrics = {
            'observation_age_turns': age_turns,
            'observation_age_seconds': difference(times['applied_seconds'], times['observed_seconds']),
            'pre_request_seconds': difference(times['request_started_seconds'], times['observed_seconds']),
            'inference_seconds': difference(times['response_finished_seconds'], times['request_started_seconds']),
            'alignment_wait_seconds': difference(times['applied_seconds'], times['response_finished_seconds']),
            'traffic_changed': None if supplied_traffic is None or action_traffic is None else supplied_traffic != action_traffic,
        }
        for saved, computed in (('latency_seconds', 'inference_seconds'),
                                ('observation_age_seconds', 'observation_age_seconds'),
                                ('observation_age_turns', 'observation_age_turns')):
            consistent(decision.get(saved), metrics[computed], saved)
        results.append({'decision_id': identity, 'status': status,
                        'action_tick_found': step is not None, **metrics,
                        'missing_metrics': [key for key, value in metrics.items() if value is None]})
    if set(by_id) - seen:
        raise ValueError('action tick references unknown decision')
    keys = ('observation_age_turns', 'observation_age_seconds', 'pre_request_seconds',
            'inference_seconds', 'alignment_wait_seconds', 'traffic_changed')
    return {'decision_count': len(results), 'decisions_field_present': 'decisions' in episode,
            'steps_field_present': 'steps' in episode,
            'missing_counts': {key: sum(row[key] is None for row in results) for key in keys},
            'decisions': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('episodes', nargs='+', type=Path)
    args = parser.parse_args()
    reports = []
    try:
        for path in args.episodes:
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rt', encoding='utf-8') as stream:
                reports.append({'source': str(path), **audit_episode(json.load(stream))})
    except (ValueError, OSError, TypeError, AttributeError) as error:
        parser.exit(1, f'audit failed for {path}: {error}\n')
    print(json.dumps(reports, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
