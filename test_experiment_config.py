"""Offline recipe validation; python -m unittest test_experiment_config."""
import copy
import json
from pathlib import Path
import unittest
from experiment_config import load_config, validate_config

ROOT = Path(__file__).resolve().parent


def recipe():
    return load_config(ROOT/'configs/qwen_boolean.json', ready=True)


class ConfigTests(unittest.TestCase):
    def test_roundtrip_no_mutation_and_draft_readiness(self):
        c = recipe()
        before = copy.deepcopy(c)
        self.assertEqual(validate_config(json.loads(json.dumps(c)), True), c)
        self.assertEqual(c, before)
        path = ROOT/'configs/native_effort_draft.json'
        self.assertIsNone(load_config(path)['model']['expected_digest'])
        with self.assertRaises(ValueError):
            load_config(path, ready=True)

    def test_invalid_budgets_timeouts_and_unsupported_options(self):
        for key, value in [('num_predict',0),('num_predict',True),('num_ctx',1.5),
                           ('seed',False),('temperature',float('nan')),('top_magic',1)]:
            c = recipe()
            c['generation'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_config(c)
        for timeout in [0,-1,True,float('inf'),float('nan')]:
            c = recipe()
            c['request_timeout'] = timeout
            with self.assertRaises(ValueError):
                validate_config(c)

    def test_splits_and_unrecognized_fields(self):
        for mutate in [lambda c:c.update(output_path='incidental'),
                       lambda c:c['starts']['evaluation'].append(0),
                       lambda c:c.update(provider='paid_api'),
                       lambda c:c.update(modes={'high':{'control':'effort','value':'high'}})]:
            c = recipe()
            mutate(c)
            with self.assertRaises(ValueError):
                validate_config(c)
