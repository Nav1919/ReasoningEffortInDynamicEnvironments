"""Shared, explicit experiment recipes. CLI: python experiment_config.py FILE.

Tests: test_experiment_config.py. Validation is offline; readiness is not proof
of a model match or scientific validity. No implicit provider defaults are added.
"""
import argparse
import copy
import json
import math
from pathlib import Path
from model_capabilities import OPTIONS, validate_modes

FIELDS = {'design', 'schema_version', 'experiment_name', 'provider', 'model', 'modes',
          'prompt', 'generation', 'request_timeout', 'environment',
          'tick_intervals', 'waiting_action', 'starts', 'scheduling_seed', 'replicates'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum=1):
    require(type(value) is int and value >= minimum, 'Expected integer >= '+str(minimum))


def positive(value):
    require(type(value) in (int, float) and math.isfinite(value) and value > 0,
            'Expected finite positive number')


def validate_config(config, ready=False):
    require(isinstance(config, dict) and set(config) == FIELDS, 'Unexpected/missing recipe fields')
    c = copy.deepcopy(config)
    require(type(c['schema_version']) is int and c['schema_version'] == 1, 'Unsupported schema')
    require(isinstance(c['experiment_name'], str) and bool(c['experiment_name']), 'Name required')
    require(c['provider'] == 'ollama', 'Only authorized Ollama provider is implemented')
    require(c['design'] in ('frozen-six-v1','live-starts-v1'), 'Unknown experiment design')
    model = c['model']
    require(isinstance(model, dict) and set(model) == {'tag', 'expected_digest', 'capability_profile'}, 'Explicit model fields required')
    require(isinstance(model['tag'], str) and bool(model['tag']), 'Exact model tag required')
    digest = model['expected_digest']
    require(digest is None or (isinstance(digest, str) and len(digest) == 64
            and all(x in '0123456789abcdef' for x in digest)), 'Expected SHA256 digest or null draft')
    require(not ready or digest is not None, 'Model selection unresolved: expected digest is null')
    validate_modes(model['capability_profile'], c['modes'])
    require(c['prompt'] == {'variant':'progress_source_v2', 'version':2, 'board':'full'},
            'New controlled comparisons require the audited versioned full-board prompt')
    generation = c['generation']
    require(isinstance(generation, dict) and set(generation) <= OPTIONS
            and 'num_predict' in generation, 'Unsupported/missing generation options')
    for key in ('num_predict', 'num_ctx'):
        if key in generation:
            integer(generation[key])
    if 'seed' in generation:
        integer(generation['seed'], 0)
    if 'temperature' in generation:
        value = generation['temperature']
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0, 'Invalid temperature')
    positive(c['request_timeout'])
    require(c['environment'] == {'id':'Freeway-v0', 'source_sha256':
            '9a0a252cb1db44830920268f745f0dadd3a00e4ccbe6863b36a38daa3126367a'}, 'Pinned Freeway required')
    require(isinstance(c['tick_intervals'], list) and bool(c['tick_intervals']), 'Intervals required')
    for interval in c['tick_intervals']:
        positive(interval)
    require(len(set(c['tick_intervals'])) == len(c['tick_intervals']), 'Duplicate intervals')
    require(c['waiting_action'] == 'S', 'Only audited waiting action S is supported')
    require(isinstance(c['starts'], dict) and set(c['starts']) == {'development', 'evaluation'}, 'Explicit seed splits required')
    selectors = []
    for split in c['starts'].values():
        require(isinstance(split, list) and bool(split), 'Each split needs selectors')
        for selector in split:
            integer(selector, 0)
            require(selector <= 7, 'Freeway selector must be 0..7')
            selectors.append(selector)
    require(len(selectors) == len(set(selectors)), 'Overlapping selectors')
    require(set(range(5)) <= set(c['starts']['development']), 'Inspected selectors 0..4 are development')
    integer(c['scheduling_seed'], 0)
    integer(c['replicates'])
    return c


def load_config(path, ready=False):
    return validate_config(json.loads(Path(path).read_text()), ready=ready)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--ready', action='store_true')
    args = parser.parse_args()
    print(json.dumps(load_config(args.config, args.ready), indent=2))
