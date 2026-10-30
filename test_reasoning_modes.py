"""Offline mode and historical-request compatibility checks.
Run: python -m unittest test_reasoning_modes.py
"""
import copy
import json
from types import SimpleNamespace
import unittest
from reasoning_modes import modes_for, thinking_value
from run_model_freeway import build_request


class ReasoningModeTests(unittest.TestCase):
    def test_explicit_controls_and_json_roundtrip(self):
        for control in ['boolean', 'effort']:
            modes = modes_for(control)
            for mode in json.loads(json.dumps(modes)).values():
                self.assertEqual(thinking_value(mode), mode['value'])
        self.assertIs(thinking_value(modes_for('boolean')['off']), False)
        self.assertEqual(thinking_value(modes_for('effort')['low']), 'low')

    def test_reject_confused_controls(self):
        for mode in [{}, {'control':'boolean','value':'low'},
                     {'control':'effort','value':True},
                     {'control':'effort','value':'max'},
                     {'control':'budget','value':2048}]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                thinking_value(mode)

    def test_definitions_do_not_share_mutable_state(self):
        modes = modes_for('boolean')
        modes['off']['value'] = True
        self.assertIs(modes_for('boolean')['off']['value'], False)

    def test_historical_qwen_requests_change_only_think(self):
        observation = {'state_string':'BOARD', 'state':{'player_states':0}}
        saved = copy.deepcopy(observation)
        args = SimpleNamespace(model='qwen3:4b-q4_K_M', prompt='original',
                               board='full', tick_seconds=1.0, thinking='off')
        off = build_request(observation, args)
        args.thinking = 'on'
        on = build_request(observation, args)
        self.assertIs(off['think'], False)
        off['think'] = True
        self.assertEqual(off, on)
        self.assertEqual(observation, saved)
