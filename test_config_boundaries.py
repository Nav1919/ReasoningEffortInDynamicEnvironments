"""Reject unfair settings before a model call; run with unittest discovery.

Uses real recipe/request/identity helpers with fake metadata. No network or AI.
"""
import copy
import unittest

from experiment_config import validate_config
from experiment_identity import resolve_run
from experiment_starts import start_registry
from model_provenance import verify_model
from run_model_freeway import build_comparison_request
from test_experiment_config import recipe


class ConfigBoundaryTests(unittest.TestCase):
    def test_invalid_settings_leave_the_original_untouched(self):
        mutations = [
            lambda c: c.update(model=None),
            lambda c: c.update(starts=[]),
            lambda c: c.update(tick_intervals=[True]),
            lambda c: c.update(tick_intervals=[1, 1.0]),
            lambda c: c.update(replicates=True),
            lambda c: c['starts']['evaluation'].append(False),
            lambda c: c['model'].update(capability_profile=[]),
            lambda c: c['model'].update(expected_digest='not-a-digest'),
        ]
        for index, mutate in enumerate(mutations):
            config = recipe()
            mutate(config)
            before = copy.deepcopy(config)
            with self.subTest(change=index), self.assertRaises(ValueError):
                validate_config(config)
            self.assertEqual(config, before)

    def test_numeric_spellings_produce_identical_requests_and_ids(self):
        config = recipe()
        self.assertEqual(resolve_run(config, 'off', 1, 0),
                         resolve_run(config, 'off', 1.0, 0))
        self.assertEqual(build_comparison_request({}, config, 'off', 1),
                         build_comparison_request({}, config, 'off', 1.0))

    def test_boolean_is_not_a_time_or_start_number(self):
        for tick in [True, False, float('nan'), float('inf'), 0, -1]:
            with self.subTest(tick=tick), self.assertRaises(ValueError):
                build_comparison_request({}, recipe(), 'off', tick)
        with self.assertRaises(ValueError):
            resolve_run(recipe(), 'off', 1, True)

    def test_start_split_order_does_not_change_the_registry(self):
        config = recipe()
        reversed_config = copy.deepcopy(config)
        reversed_config['starts'] = dict(reversed(list(config['starts'].items())))
        self.assertEqual(start_registry(config), start_registry(reversed_config))

    def test_model_check_only_reads_metadata_and_never_loads_a_model(self):
        config = recipe()
        calls = []
        def provider(endpoint, payload, timeout):
            calls.append(endpoint)
            return {
                'version': {'version': '0.35.1'},
                'tags': {'models': [{'name': config['model']['tag'],
                                    'digest': 'sha256:' + config['model']['expected_digest']}]},
                'show': {'details': {'family': 'qwen3'}},
            }[endpoint]
        self.assertEqual(verify_model(config, provider)['digest'],
                         config['model']['expected_digest'])
        self.assertEqual(calls, ['version', 'tags', 'show'])

    def test_missing_or_ambiguous_model_stops_before_more_requests(self):
        for models in [[], [{'name': 'different-model', 'digest': '0' * 64}],
                       [{'name': recipe()['model']['tag'], 'digest': '0' * 64}] * 2]:
            calls = []
            def provider(endpoint, payload, timeout):
                calls.append(endpoint)
                return {'version': {'version': '0.35.1'}, 'tags': {'models': models}}[endpoint]
            with self.subTest(models=models), self.assertRaises(ValueError):
                verify_model(recipe(), provider)
            self.assertEqual(calls, ['version', 'tags'])
