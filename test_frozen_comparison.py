"""Fake-provider frozen calls; no network or sleeping."""
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from comparison_plan import build_plan
from frozen_comparison import run_frozen
from test_experiment_config import recipe


class FrozenRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = recipe()
        c['tick_intervals'] = [1]
        cls.entry = build_plan(c)['runs'][0]

    def run_case(self, path, provider, model_check=lambda c:{'metadata':{}}):
        clock = itertools.count()
        return run_frozen(self.entry,path,provider,model_check,lambda c:{},lambda:next(clock))

    def test_valid_missing_and_zero_counts(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'run.json'
            calls = []
            def provider(endpoint,payload,timeout):
                calls.append(payload)
                return dict(message={'content':'U'},done_reason='stop',eval_count=0)
            record = self.run_case(path,provider)
            self.assertEqual(record['run_status'],'complete')
            self.assertEqual(len(calls),2)  # warm-up, measured request
            decision = record['decisions'][0]
            self.assertTrue(decision['valid_action'])
            self.assertIsNotNone(decision['reference_outcome'])
            self.assertIsNone(decision['executed_action'])
            self.assertIsNone(decision['measurements']['input_tokens'])
            self.assertEqual(decision['measurements']['output_tokens'],0)
            self.assertEqual(json.loads(path.read_text())['plan_run_id'], self.entry['run_id'])

    def test_invalid_answer_and_setup_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            def invalid(*args,**kwargs):
                return {'message':{'content':'explanation'},'done_reason':'stop'}
            record = self.run_case(Path(temporary)/'invalid.json',invalid)
            self.assertFalse(record['decisions'][0]['valid_action'])
            self.assertIsNone(record['decisions'][0]['reference_outcome'])
            def fail(config):
                raise ValueError('Wrong installed model digest')
            record = self.run_case(Path(temporary)/'setup.json',invalid,fail)
            self.assertEqual(record['run_status'],'setup_failed')
            self.assertEqual(record['decisions'],[])
