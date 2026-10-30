"""Summaries with explicit denominators and unavailable measurements.

Tests: test_comparison_metrics.py. Warm-up is excluded from measured decisions.
"""
from collections import Counter
import statistics
from comparison_summary import comparison_summary
from freeway_study import write_csv, write_json


def rate(values):
    return dict(numerator=sum(values),denominator=len(values),
                fraction=sum(values)/len(values) if values else None)


def write_comparison_summary(folder):
    summary = comparison_summary(folder)
    records = summary.pop('records_by_mode')
    rows = []
    for mode, entries in records.items():
        runs = [entry['record'] for entry in entries if entry['record']]
        decisions = [d for run in runs for d in run.get('decisions',[])]
        latencies = [d['latency_seconds'] for d in decisions if d.get('latency_seconds') is not None]
        tokens, missing, available = {}, {}, {}
        for name in ['input_tokens','output_tokens','reasoning_tokens']:
            values = [d.get('measurements',{}).get(name) for d in decisions]
            measured = [v for v in values if v is not None]
            tokens[name] = sum(measured) if measured else None
            available[name] = len(measured)
            missing[name] = len(values)-len(measured)
        rows.append(dict(mode=mode,comparison_id=summary['comparison_id'],
            run_configuration_ids=sorted({r['resolved']['run_configuration_id'] for r in runs}),
            planned=len(entries),status_counts=dict(Counter(e['status'] for e in entries)),
            requests_attempted=len(decisions),
            valid_action_rate=rate([d['valid_action'] for d in decisions]),
            request_status_counts=dict(Counter(d['request_status'] for d in decisions)),
            immediate_safety=rate([d['immediate_safe'] for d in decisions if d.get('immediate_safe') is not None]),
            relevant_choice=rate([d['relevant_choice'] for d in decisions if d.get('relevant_choice') is not None]),
            median_latency_seconds=statistics.median(latencies) if latencies else None,
            output_token_totals=tokens,measurement_available=available,measurement_missing=missing,
            crossing_rate=rate([r.get('episode_outcome')=='crossed' for r in runs
                                if r.get('design')=='live-starts-v1' and r['run_status']=='complete'])))
    summary['metrics']=rows
    write_json(folder/'comparison_summary.json',summary)
    write_csv(folder/'comparison_modes.csv',rows)
    return summary
