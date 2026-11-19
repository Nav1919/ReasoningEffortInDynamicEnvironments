"""Strict offline matched-mode analysis (standard library only).

Run: python paired_comparison.py INPUT.json --output REPORT.json
Add --csv-output PAIRS.csv for a flat paired table. INPUT may also be CSV.
Inputs: explicit controlled run records; outputs: retained records, per-start
mode differences and coverage. No simulator/model calls. See schema and limits in
docs/weekend/paired-comparison.md. Tested by test_paired_comparison.py with
python -m unittest test_paired_comparison -v (synthetic fixtures only).
"""
import argparse
import csv
import json
import math
from pathlib import Path

CONTROLS = ('scenario', 'start', 'difficulty', 'pressure',
            'observation_condition', 'model_identity')
METRICS = ('outcome', 'seconds', 'tokens')
FIELDS = set(CONTROLS) | {'mode', 'shared_settings', 'mode_settings', 'status',
                          'error', 'evidence_kind'} | set(METRICS)


def canonical(value):
    """Compare settings structurally, rejecting non-JSON and nonfinite values."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':'))


def unique_object(items):
    """Do not let a JSON parser silently overwrite a conflicting setting."""
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def load_records(path):
    """Read a JSON array or CSV; CSV settings cells contain JSON objects."""
    path = Path(path)
    if path.suffix.lower() == '.csv':
        with path.open(newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError('missing or duplicate CSV columns')
            if set(reader.fieldnames) != FIELDS:
                raise ValueError('CSV must contain exactly the documented columns')
            records = list(reader)
        for row in records:
            for field in ('shared_settings', 'mode_settings') + METRICS:
                value = row.get(field)
                row[field] = json.loads(value, object_pairs_hook=unique_object) if value else None
        return records
    with path.open(encoding='utf-8') as handle:
        return json.load(handle, object_pairs_hook=unique_object)


# Validation is deliberately separate from arithmetic: unknown fields, retries,
# mixed models and configuration drift must not silently enter a fair comparison.
def analyze(records):
    """Validate records and return deliberate-minus-quick paired differences."""
    if not isinstance(records, list) or not records:
        raise ValueError('expected a nonempty record array')
    groups, settings, models, kinds = {}, {}, set(), set()
    retained = []
    for record in records:
        if not isinstance(record, dict) or set(record) != FIELDS:
            raise ValueError('each record must contain exactly the documented fields')
        row = dict(record)
        for field in CONTROLS:
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f'{field} must be an explicit nonempty string')
        if row['mode'] not in ('quick', 'deliberate'):
            raise ValueError('mode must be quick or deliberate')
        if row['status'] not in ('completed', 'failed', 'missing'):
            raise ValueError('invalid status')
        if row['evidence_kind'] not in ('synthetic', 'measured'):
            raise ValueError('evidence_kind must be synthetic or measured')
        if not isinstance(row['error'], str):
            raise ValueError('error must be a string (empty for completed)')
        if (row['status'] == 'completed') != (row['error'] == ''):
            raise ValueError('failed/missing records need a reason; completed records cannot have one')
        for field in ('shared_settings', 'mode_settings'):
            if not isinstance(row[field], dict) or not row[field]:
                raise ValueError(f'{field} must be a nonempty explicit object')
            canonical(row[field])
        for field in METRICS:
            value = row[field]
            if value is not None:
                if type(value) not in (int, float) or not math.isfinite(value):
                    raise ValueError(f'{field} must be finite numeric or null')
                if field != 'outcome' and value < 0:
                    raise ValueError(f'{field} cannot be negative')
                if field == 'tokens' and type(value) is not int:
                    raise ValueError('tokens must be an integer count')
        if row['status'] == 'completed' and row['outcome'] is None:
            raise ValueError('completed records require a measured numeric outcome')
        if row['status'] == 'missing' and any(row[f] is not None for f in METRICS):
            raise ValueError('missing records cannot have measurements')
        mode = row['mode']
        config = canonical(row['mode_settings'])
        if mode in settings and settings[mode] != config:
            raise ValueError(f'conflicting settings within {mode} mode')
        settings[mode] = config
        models.add(row['model_identity'])
        kinds.add(row['evidence_kind'])
        key = tuple(row[f] for f in CONTROLS)
        group = groups.setdefault(key, {})
        if mode in group:
            raise ValueError('duplicate controlled run identity (including retries)')
        if group and canonical(next(iter(group.values()))['shared_settings']) != canonical(row['shared_settings']):
            raise ValueError('conflicting shared settings for matched controls')
        group[mode] = row
        retained.append(row)
    if len(models) != 1 or len(kinds) != 1:
        raise ValueError('one frozen model and one evidence kind required per analysis')
    if len(settings) == 2 and settings['quick'] == settings['deliberate']:
        raise ValueError('quick and deliberate must declare distinct mode settings')

    # Keep every observed/planned cell. Missing counterparts are explicit in the
    # table, never zero-imputed; failed partial measurements remain in records.
    pairs = []
    coverage = {mode: {status: 0 for status in ('completed', 'failed', 'missing')}
                for mode in ('quick', 'deliberate')}
    counts = {field: 0 for field in METRICS}
    for key, group in sorted(groups.items()):
        pair = dict(zip(CONTROLS, key))
        pair['evidence_kind'] = next(iter(kinds))
        for mode in coverage:
            status = group[mode]['status'] if mode in group else 'missing'
            pair[mode + '_status'] = status
            coverage[mode][status] += 1
            for field in METRICS:
                pair[mode + '_' + field] = group[mode][field] if mode in group else None
        complete = all(pair[m + '_status'] == 'completed' for m in coverage)
        for field in METRICS:
            q, d = pair['quick_' + field], pair['deliberate_' + field]
            difference = d - q if complete and q is not None and d is not None else None
            if difference is not None and not math.isfinite(difference):
                raise ValueError('nonfinite metric difference')
            pair[field + '_difference'] = difference
            counts[field] += difference is not None
        pairs.append(pair)
    return {'evidence_kind': next(iter(kinds)), 'difference_direction': 'deliberate-minus-quick',
            'records': retained, 'pairs': pairs,
            'coverage': {'starts': len(pairs), 'input_records': len(records),
                         'by_mode': coverage, 'paired_metrics': counts,
                         'completed_pairs': sum(all(p[m + '_status'] == 'completed'
                                                    for m in coverage) for p in pairs)}}


def main(argv=None):
    """CLI entry point; invalid input produces no report and exits nonzero."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--csv-output', type=Path)
    args = parser.parse_args(argv)
    paths = [p.resolve() for p in (args.input, args.output, args.csv_output) if p]
    if len(paths) != len(set(paths)):
        parser.error('input and output paths must be distinct')
    try:
        result = analyze(load_records(args.input))
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    if args.csv_output:
        with args.csv_output.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(result['pairs'][0]))
            writer.writeheader()
            writer.writerows(result['pairs'])


if __name__ == '__main__':
    main()
