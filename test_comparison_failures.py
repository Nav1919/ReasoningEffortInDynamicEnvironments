"""Test damaged plans and failed runs through the real comparison pipeline.

Run with unittest discovery. Fake providers replace AI calls; temporary folders
hold real plans, run records, and summaries. No network or sleeping is needed.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from comparison_execution import execute_plan
from comparison_metrics import write_comparison_summary
from comparison_plan import build_plan
from experiment_config import load_config
from test_experiment_config import ROOT, recipe


class ComparisonFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = recipe()
        config['tick_intervals'] = [1]
        cls.plan = build_plan(config)

    def prepare(self, folder, plan=None):
        (folder / 'plan.json').write_text(json.dumps(plan or self.plan))

    def execute(self, folder, provider, limit=1):
        return execute_plan(folder, limit=limit, provider=provider,
            model_check=lambda c: {'digest': c['model']['expected_digest']},
            source_check=lambda c: {'freeway_source_sha256': c['environment']['source_sha256'],
                                    'source_sha256': {'fake_provider_test': 'v1'}})

    def test_changed_plan_is_rejected_before_any_model_call(self):
        for field in ['request', 'run_id']:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                plan = copy.deepcopy(self.plan)
                if field == 'request':
                    plan['runs'][0]['request']['think'] = 'unexpected'
                else:
                    plan['runs'][0]['run_id'] = 'unexpected'
                self.prepare(folder, plan)
                calls = []
                with self.subTest(field=field), self.assertRaises(ValueError):
                    self.execute(folder, lambda *a, **k: calls.append(a))
                self.assertEqual(calls, [])
                self.assertFalse((folder / 'execution.json').exists())

    def test_answer_timeout_stops_and_keeps_all_unrun_questions(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.prepare(folder)
            calls = []
            def provider(endpoint, payload, timeout):
                calls.append(payload)
                if len(calls) == 1:
                    return {'message': {'content': 'S'}, 'done_reason': 'stop'}
                raise TimeoutError('timed out')
            execution = self.execute(folder, provider, limit=12)
            self.assertEqual(len(calls), 2)  # one warm-up, one failed question
            self.assertEqual(execution['status'], 'stopped')
            self.assertEqual(execution['runs'][0]['status'], 'failed')
            self.assertTrue(all(r['status'] == 'planned' for r in execution['runs'][1:]))
            report = write_comparison_summary(folder)
            self.assertEqual(sum(m['requests_attempted'] for m in report['metrics']), 1)
            self.assertEqual(sum(m['valid_action_rate']['numerator'] for m in report['metrics']), 0)
            self.assertEqual(report['planned_runs'], len(self.plan['runs']))

    def test_unexpected_load_reply_stops_before_any_question(self):
        config = load_config(ROOT / 'configs/native_effort_draft.json')
        config.update(schema_version=2, warmup_policy='load_once')
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.prepare(folder, build_plan(config))
            calls = []
            def provider(endpoint, payload, timeout):
                calls.append(endpoint)
                return {'message': {'content': 'U'}, 'done_reason': 'stop'}
            execution = self.execute(folder, provider, limit=18)
            self.assertEqual(calls, ['generate'])
            self.assertEqual(execution['runs'][0]['status'], 'setup_failed')
            self.assertTrue(all(r['status'] == 'planned' for r in execution['runs'][1:]))
            report = write_comparison_summary(folder)
            self.assertEqual(sum(m['requests_attempted'] for m in report['metrics']), 0)

    def test_execution_from_another_plan_cannot_be_summarized(self):
        for field in ['comparison_id', 'runs']:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                self.prepare(folder)
                self.execute(folder, lambda *a, **k: {'message': {'content': 'S'}, 'done_reason': 'stop'})
                path = folder / 'execution.json'
                execution = json.loads(path.read_text())
                if field == 'comparison_id':
                    execution[field] = 'another-comparison'
                else:
                    execution[field].pop()
                path.write_text(json.dumps(execution))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    write_comparison_summary(folder)

    def test_missing_log_stays_visible_as_a_missing_partner(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.prepare(folder)
            execution = self.execute(folder, lambda *a, **k: {'message': {'content': 'U'}, 'done_reason': 'stop'})
            (folder / execution['runs'][0]['log']).unlink()
            report = write_comparison_summary(folder)
            self.assertEqual(sum(m['statuses'].get('missing_log', 0)
                                 for m in report['mode_counts'].values()), 1)
            self.assertEqual(len(report['pairs'][0]['missing_partners']), 2)

    def test_completed_runs_from_different_code_cannot_be_pooled(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.prepare(folder)
            execution = self.execute(folder, lambda *a, **k: {'message': {'content': 'U'}, 'done_reason': 'stop'}, limit=2)
            path = folder / execution['runs'][1]['log']
            record = json.loads(path.read_text())
            record['provenance']['source']['source_sha256'] = {'fake_provider_test': 'v2'}
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'different runnable source'):
                write_comparison_summary(folder)

    def test_invalid_answers_are_attempts_but_never_successes(self):
        for response in [None, {'message': {'content': 'U'}, 'done_reason': 'length'},
                         {'message': {'content': 'Move up'}, 'done_reason': 'stop'}]:
            with tempfile.TemporaryDirectory() as temporary:
                folder = Path(temporary)
                self.prepare(folder)
                self.execute(folder, lambda *a, **k: response)
                report = write_comparison_summary(folder)
                with self.subTest(response=response):
                    self.assertEqual(sum(m['requests_attempted'] for m in report['metrics']), 1)
                    self.assertEqual(sum(m['valid_action_rate']['numerator'] for m in report['metrics']), 0)
                    self.assertEqual(sum(m['crossing_rate']['denominator'] for m in report['metrics']), 0)
