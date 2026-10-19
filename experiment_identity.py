"""Stable scientific identities and resolved records; tests: test_experiment_identity.

Comparison = full validated recipe + instruction fingerprints for all intervals.
Run configuration = comparison + selected mode. Paths/timestamps are not inputs.
Starts, conditions, replicates, and attempts identify individual planned runs.
"""
import hashlib
import json
from experiment_config import validate_config, integer, positive
from run_model_freeway import prompt_record


def fingerprint(value):
    canonical = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def resolve_run(config, mode, tick_seconds, selector, replicate=0):
    """Return a detached complete recipe with explicit run selections and IDs."""
    c = validate_config(config)
    positive(tick_seconds)
    integer(selector, 0)
    if mode not in c['modes'] or tick_seconds not in c['tick_intervals']:
        raise ValueError('Mode/condition is not in recipe')
    if selector not in c['starts']['development']:
        raise ValueError('Only development starts are executable in Step 2')
    if type(replicate) is not int or not 0 <= replicate < c['replicates']:
        raise ValueError('Replicate is not in recipe')
    tick_seconds = next(tick for tick in c['tick_intervals'] if tick == tick_seconds)
    prompts = [prompt_record(c, tick) for tick in c['tick_intervals']]
    comparison_id = fingerprint(dict(recipe=c, prompts=prompts))
    run_configuration_id = fingerprint(dict(comparison_id=comparison_id,
                                             selected_mode=mode, mode=c['modes'][mode]))
    return dict(config=c, comparison_id=comparison_id,
                run_configuration_id=run_configuration_id, selected_mode=mode,
                tick_seconds=tick_seconds, requested_selector=selector,
                replicate=replicate, prompt=prompt_record(c, tick_seconds))
