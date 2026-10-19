"""Offline end-to-end summary checks: invalid action versus missing counts."""
import json
from pathlib import Path
import tempfile
import unittest
from comparison_execution import execute_plan
from comparison_metrics import write_comparison_summary
import test_comparison_execution as execution_tests


class MetricsTests(unittest.TestCase):
    def test_validity_and_missing_counts_have_separate_denominators(self):
        execution_tests.ExecutionTests.setUpClass()
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'plan.json').write_text(json.dumps(execution_tests.ExecutionTests.plan))
            calls=[]
            def provider(*args,**kwargs):
                calls.append(1)
                # The two warm-ups don't enter measured counts.
                content='prose' if len(calls)==4 else 'S'
                return dict(message={'content':content},done_reason='stop',eval_count=0)
            execute_plan(folder,limit=2,provider=provider,
                model_check=lambda c:{'digest':c['model']['expected_digest']},
                source_check=lambda c:dict(freeway_source_sha256=c['environment']['source_sha256'],
                                           source_sha256={'fake_provider_test':'v1'}))
            summary=write_comparison_summary(folder)
            rows=summary['metrics']
            self.assertEqual(sum(r['requests_attempted'] for r in rows),2)
            self.assertEqual(sum(r['valid_action_rate']['numerator'] for r in rows),1)
            self.assertTrue(all(r['output_token_totals']['output_tokens']==0 for r in rows))
            self.assertTrue(all(r['output_token_totals']['input_tokens'] is None for r in rows))
            self.assertTrue(all(r['measurement_missing']['input_tokens']==1 for r in rows))
            self.assertTrue(all(r['crossing_rate']['denominator']==0 for r in rows))
            self.assertTrue((folder/'comparison_modes.csv').exists())
            self.assertNotIn('records_by_mode',summary)
            self.assertEqual(summary,write_comparison_summary(folder))

    def test_plan_without_calls_has_no_invented_measurements(self):
        execution_tests.ExecutionTests.setUpClass()
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            (folder/'plan.json').write_text(json.dumps(execution_tests.ExecutionTests.plan))
            report=write_comparison_summary(folder)
            self.assertTrue(all(r['valid_action_rate']['denominator']==0 for r in report['metrics']))
            self.assertTrue(all(r['median_latency_seconds'] is None for r in report['metrics']))
