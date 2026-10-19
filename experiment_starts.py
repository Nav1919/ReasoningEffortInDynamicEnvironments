"""Verify selector/actual-start separation. CLI: python experiment_starts.py CONFIG.

Only initial states are inspected; reserved starts are never stepped or queried
with a model. Tests: test_experiment_starts.py.
"""
import argparse
import json
from experiment_config import load_config, validate_config
from experiment_identity import fingerprint
from freeway_study import internal_state, recreate


def validate_start_records(records):
    seeds, states, selectors = set(), set(), set()
    for record in records:
        if record['split'] not in ('development', 'evaluation'):
            raise ValueError('Unknown split')
        if (record['actual_seed'] in seeds or record['initial_state_sha256'] in states
                or record['requested_selector'] in selectors):
            raise ValueError('Overlapping actual seeds or initial states across starts')
        seeds.add(record['actual_seed'])
        states.add(record['initial_state_sha256'])
        selectors.add(record['requested_selector'])
    return records


def start_registry(config, factory=recreate):
    c = validate_config(config)
    records = []
    for split, selectors in c['starts'].items():
        for selector in selectors:
            env, actual = factory(selector, '')
            records.append(dict(requested_selector=selector, actual_seed=actual,
                initial_state_sha256=fingerprint(internal_state(env)), split=split))
    return validate_start_records(records)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    args = parser.parse_args()
    print(json.dumps(start_registry(load_config(args.config)), indent=2))
