"""Offline Freeway configuration and decision-record validation (Python 3.10+).

Usage: python3 -B src/freeway_schema.py configs/freeway.json
Inputs: JSON object manifest; optional JSON array of decision records as second arg.
Output: validation summary; invalid inputs exit nonzero. No simulator/model calls.
Tests: ../tests/test_freeway_schema.py; protocol: ../docs/offline-skeleton.md.
"""

import json
import math
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def object_value(value, label):
    require(isinstance(value, dict), f'{label} must be an object')


def text_value(value, label):
    require(isinstance(value, str) and bool(value.strip()), f'{label} must be nonempty text')


def number(value, label, integer=False):
    require(type(value) in ((int,) if integer else (int, float)), f'{label} has invalid type')
    require(math.isfinite(value) and value >= 0, f'{label} must be finite and nonnegative')


def validate_manifest(manifest, ready=False):
    """Validate a draft, or require human selections with ready=True.

    Starts are one global seed namespace: neither IDs nor seeds may cross splits.
    Empty selections are valid drafts, never an executable experiment plan.
    """
    object_value(manifest, 'manifest')
    require(manifest['schema_version'] == 1, 'unsupported schema version')
    require(manifest['environment'] == 'RealtimeGym/Freeway', 'Freeway only')
    model = manifest['model_identifier']
    if model is not None:
        text_value(model, 'model_identifier')
    modes = manifest['modes']
    object_value(modes, 'modes')
    require(set(modes) == {'quick', 'deliberate'}, 'require quick and deliberate')
    for value in modes.values():
        require(value is None or isinstance(value, dict), 'mode configuration must be object or null')
    for field in ('difficulties', 'pressures'):
        require(isinstance(manifest[field], dict), f'{field} must map labels to exact settings')
        for label, value in manifest[field].items():
            text_value(label, field)
            object_value(value, field)
    delay = manifest['older_view_seconds']
    if delay is not None:
        number(delay, 'older_view_seconds')
    starts = manifest['starts']
    require(isinstance(starts, dict) and set(starts) == {'development', 'held_out'}, 'require separate start splits')
    ids, seeds = set(), set()
    for split, entries in starts.items():
        require(isinstance(entries, list), 'starts must be lists')
        for entry in entries:
            object_value(entry, 'start')
            text_value(entry['start_id'], 'start_id')
            number(entry['seed'], 'seed', integer=True)
            require(entry['start_id'] not in ids and entry['seed'] not in seeds, 'duplicate start ID or seed across manifest')
            ids.add(entry['start_id'])
            seeds.add(entry['seed'])
    if ready:
        require(model is not None and all(modes.values()), 'human model/mode decisions required')
        require(modes['quick'] != modes['deliberate'], 'modes must differ')
        require(bool(manifest['difficulties']) and bool(manifest['pressures']) and delay is not None,
                'human condition decisions required')
        require(all(starts.values()), 'human start/split decisions required')
    return manifest


def validate_record(record, manifest, purpose='evaluation'):
    """Validate one decision, retaining missing measurements only with failures.

    Times are seconds on the same monotonic clock. Age is measured at action
    submission, so it includes both deliberately old views and decision latency.
    Development access explicitly rejects held-out data; evaluation is read-only.
    """
    validate_manifest(manifest, ready=True)
    object_value(record, 'record')
    require(purpose in ('development', 'evaluation'), 'invalid access purpose')
    require(record['schema_version'] == 1, 'unsupported record version')
    text_value(record['run_id'], 'run_id')
    number(record['decision_index'], 'decision_index', integer=True)
    number(record['seed'], 'seed', integer=True)
    split = record['split']
    require(split in manifest['starts'], 'unknown split')
    require(purpose != 'development' or split == 'development', 'held-out data forbidden for development')
    require({'start_id': record['start_id'], 'seed': record['seed']} in manifest['starts'][split], 'start/seed does not belong to split')
    require(record['model_identifier'] == manifest['model_identifier'], 'model mismatch')
    mode = record['mode']
    require(mode in manifest['modes'], 'unknown mode')
    require(record['mode_configuration'] == manifest['modes'][mode], 'mode configuration mismatch')
    for field, catalog in (('difficulty', 'difficulties'), ('pressure', 'pressures')):
        require(record[field] in manifest[catalog], f'unknown {field}')
    failures = record['failures']
    require(isinstance(failures, list), 'failures must be a list')
    for failure in failures:
        text_value(failure, 'failure')
    require(record['action'] in ('U', 'D', 'S') or (record['action'] is None and failures), 'action must be U/D/S or failed missing action')
    require(record['outcome'] is None or isinstance(record['outcome'], dict), 'outcome must be simulator object or null')
    require(record['outcome'] is not None or failures, 'missing outcome needs failure')
    for field in ('input_tokens', 'output_tokens', 'reasoning_tokens', 'elapsed_seconds',
                  'observation_time_seconds', 'action_time_seconds', 'observation_age_seconds'):
        value = record[field]
        if value is None:
            require(bool(failures), f'missing {field} needs failure')
        else:
            number(value, field, integer=field.endswith('tokens'))
    observed, acted, age = (record[k] for k in ('observation_time_seconds', 'action_time_seconds', 'observation_age_seconds'))
    if observed is not None and acted is not None:
        require(acted >= observed, 'action precedes observation')
        if age is not None:
            require(math.isclose(age, acted - observed, abs_tol=1e-6, rel_tol=1e-9), 'inconsistent observation age')
    return record


# The CLI validates supplied data only; it never creates records or runs games.
def main():
    with open(sys.argv[1], encoding='utf-8') as stream:
        manifest = json.load(stream)
    validate_manifest(manifest)
    if len(sys.argv) > 2:
        with open(sys.argv[2], encoding='utf-8') as stream:
            records = json.load(stream)
        require(isinstance(records, list), 'records must be a JSON array')
        for record in records:
            validate_record(record, manifest)
        print(f'Validated {len(records)} records')
    else:
        print('Valid draft manifest; this does not establish experiment readiness')


if __name__ == '__main__':
    main()
