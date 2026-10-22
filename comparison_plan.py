"""Offline matching run plans; tests: test_comparison_plan.py.

Frozen design: first two development selectors in each existing diagnostic
category, independent of model outputs. Live design: all development starts.
"""
import copy
import random
from experiment_config import validate_config, integer
from model_capabilities import profile_definition
from reasoning_modes import thinking_value
from experiment_identity import fingerprint, resolve_run
from experiment_starts import start_registry
from freeway_study import build_situations, recreate
from run_model_freeway import build_comparison_request


def build_plan(config, attempt=1):
    c = validate_config(config)
    integer(attempt)
    registry = start_registry(c)
    if c['design'] == 'frozen-six-v1':
        cases = build_situations()
        situations = [case for category in ['safe_forward','dangerous_forward','waiting_useful']
                      for case in sorted((s for s in cases if s['category']==category),
                                         key=lambda s:s['requested_seed'])[:2]]
    else:
        situations = []
        for selector in c['starts']['development']:
            env, actual = recreate(selector, '')
            situations.append(dict(id=f'start_{selector}', requested_seed=selector,
                actual_seed=actual, preceding_actions='', observation=copy.deepcopy(env.observe())))
    random.Random(c['scheduling_seed']).shuffle(situations)
    order = profile_definition(c['model']['capability_profile'])['values']
    modes = sorted(c['modes'], key=lambda mode:order.index(thinking_value(c['modes'][mode])))
    runs = []
    for replicate in range(c['replicates']):
        for tick in c['tick_intervals']:
            for index, situation in enumerate(situations):
                start = next(s for s in registry if s['requested_selector']==situation['requested_seed'])
                offset = (index + replicate + c['scheduling_seed']) % len(modes)
                for mode in modes[offset:]+modes[:offset]:
                    resolved = resolve_run(c, mode, tick, situation['requested_seed'], replicate)
                    identity = dict(comparison=resolved['comparison_id'], mode=mode, start=start,
                        situation_sha256=fingerprint(situation['observation']),
                        tick_seconds=tick, replicate=replicate, attempt=attempt)
                    runs.append(dict(run_id=fingerprint(identity), status='planned', attempt=attempt,
                        resolved=resolved, start=start, situation=copy.deepcopy(situation),
                        request=build_comparison_request(situation['observation'], c, mode, tick)))
    return dict(plan_version=1, design=c['design'], config=c,
                comparison_id=runs[0]['resolved']['comparison_id'], starts=registry, runs=runs)
