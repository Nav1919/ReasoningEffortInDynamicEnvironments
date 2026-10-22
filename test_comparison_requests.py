"""Offline request equality and prompt preservation; no model calls."""
import copy
from pathlib import Path
import unittest
from experiment_config import load_config
from test_experiment_config import recipe
from run_model_freeway import build_comparison_request, build_prompt, prompt_record


class RequestFairnessTests(unittest.TestCase):
    def test_native_and_boolean_differ_only_in_think(self):
        native = load_config(Path(__file__).parent/'configs/native_effort_draft.json')
        for config in [native, recipe()]:
            observation = {'state_string':'BOARD', 'state':{'player_states':3,'car_states':[]}}
            before = copy.deepcopy((config, observation))
            requests = [build_comparison_request(observation, config, mode, 1)
                        for mode in config['modes']]
            values = [r.pop('think') for r in requests]
            self.assertEqual(len(set((type(v),v) for v in values)), len(values))
            self.assertTrue(all(r == requests[0] for r in requests))
            self.assertEqual((config, observation), before)
            self.assertEqual(requests[0]['options']['num_predict'], 2048)

    def test_invalid_selection_and_template_version(self):
        c = recipe()
        for mode, tick in [('high',1),('off',3)]:
            with self.assertRaises(ValueError):
                build_comparison_request({}, c, mode, tick)
        record = prompt_record(c, 1)
        self.assertIn('both clamp', record['instruction_template'])
        self.assertNotIn('both clamp', build_prompt({}, 1, 'progress_source'))
        self.assertEqual(record, prompt_record(copy.deepcopy(c), 1))
        self.assertNotEqual(record['template_sha256'], prompt_record(c, 2)['template_sha256'])
        content = build_comparison_request({'marker':7}, c, 'off', 1)['messages'][0]['content']
        self.assertTrue(content.startswith(record['instruction_template']))
        self.assertTrue(content.endswith('{"marker": 7}'))
