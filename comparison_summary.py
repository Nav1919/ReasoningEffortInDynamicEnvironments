"""Check saved comparison compatibility and expose every missing partner.

No model calls. Tests: test_comparison_summary.py. Historical summaries are kept
in freeway_study.summarize and are never pooled with these recipe-based runs.
"""
from collections import Counter, defaultdict
import json
from pathlib import Path
from comparison_execution import checked_plan
from experiment_identity import fingerprint


def comparison_summary(folder):
    folder = Path(folder)
    plan = checked_plan(folder)
    execution_path = folder/'execution.json'
    execution = json.loads(execution_path.read_text()) if execution_path.exists() else None
    if execution and (execution['comparison_id'] != plan['comparison_id']
                      or [r['run_id'] for r in execution['runs']] != [r['run_id'] for r in plan['runs']]):
        raise ValueError('Execution belongs to a different plan/comparison')
    statuses = {r['run_id']:r['status'] for r in execution['runs']} if execution else {}
    groups, modes, source_signatures = {}, defaultdict(list), set()
    for entry in plan['runs']:
        mode = entry['resolved']['selected_mode']
        status = statuses.get(entry['run_id'],'planned')
        log = folder/'runs'/(entry['run_id']+'.json')
        record = json.loads(log.read_text()) if log.exists() else None
        if record:
            if fingerprint(record['resolved']) != fingerprint(entry['resolved']):
                raise ValueError('Run settings are incompatible with the saved comparison')
            if record['run_status'] == 'complete':
                model = record['provenance']['model']
                source = record['provenance']['source']
                if (model.get('digest') != plan['config']['model']['expected_digest']
                        or source.get('freeway_source_sha256') != plan['config']['environment']['source_sha256']):
                    raise ValueError('Actual model/environment identity is incompatible')
                source_signatures.add(fingerprint(source.get('source_sha256')))
            if record['run_status'] != status:
                status = 'inconsistent_record'
        elif status != 'planned':
            status = 'missing_log'
        actual_start = entry['start']
        key = fingerprint(dict(comparison=plan['comparison_id'], actual_start=actual_start,
            situation=fingerprint(entry['situation']['observation']),
            tick=entry['resolved']['tick_seconds'], replicate=entry['resolved']['replicate'],
            attempt=entry['attempt']))
        if key not in groups:
            groups[key] = dict(actual_seed=actual_start['actual_seed'], situation=entry['situation']['id'],
                tick_seconds=entry['resolved']['tick_seconds'], replicate=entry['resolved']['replicate'],
                attempt=entry['attempt'], modes={})
        groups[key]['modes'][mode] = status
        modes[mode].append(dict(status=status, record=record))
    if len(source_signatures)>1:
        raise ValueError('Completed runs used different runnable source fingerprints')
    pairs = list(groups.values())
    for pair in pairs:
        pair['missing_partners'] = [mode for mode in plan['config']['modes']
                                    if pair['modes'].get(mode) != 'complete']
    return dict(comparison_id=plan['comparison_id'], design=plan['design'], planned_runs=len(plan['runs']),
        mode_counts={mode:dict(planned=len(rows), statuses=dict(Counter(r['status'] for r in rows)))
                     for mode, rows in modes.items()}, pairs=pairs, records_by_mode=dict(modes))
