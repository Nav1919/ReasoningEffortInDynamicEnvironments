"""Offline recipe → plan → fake calls → saved logs → checked summary."""
import json
from pathlib import Path
import tempfile
import unittest
from comparison_execution import execute_plan
from comparison_summary import comparison_summary
from test_comparison_execution import ExecutionTests


class SummaryTests(unittest.TestCase):
    def prepare(self, folder):
        c = ExecutionTests.plan if hasattr(ExecutionTests,'plan') else None
        if c is None:
            ExecutionTests.setUpClass()
        (folder/'plan.json').write_text(json.dumps(ExecutionTests.plan))
        return ExecutionTests.plan

    def test_missing_partner_and_success_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            plan=self.prepare(folder)
            before=comparison_summary(folder)
            self.assertTrue(all(len(p['missing_partners'])==2 for p in before['pairs']))
            execute_plan(folder,limit=1,
                provider=lambda *a,**k:{'message':{'content':'S'},'done_reason':'stop'},
                model_check=lambda c:{'digest':c['model']['expected_digest']},
                source_check=lambda c:dict(freeway_source_sha256=c['environment']['source_sha256'],
                                           source_sha256={'fake_provider_test':'v1'}))
            result=comparison_summary(folder)
            self.assertEqual(result['planned_runs'],len(plan['runs']))
            self.assertEqual(len(result['pairs'][0]['missing_partners']),1)
            self.assertEqual(sum(m['statuses'].get('planned',0) for m in result['mode_counts'].values()),11)

    def test_incompatible_resolved_settings_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            plan=self.prepare(folder)
            execute_plan(folder,limit=1,provider=lambda *a,**k:{'message':{'content':'U'},'done_reason':'stop'},
                model_check=lambda c:{'digest':c['model']['expected_digest']},
                source_check=lambda c:dict(freeway_source_sha256=c['environment']['source_sha256']))
            path=folder/'runs'/(plan['runs'][0]['run_id']+'.json')
            record=json.loads(path.read_text())
            record['resolved']['config']['generation']['num_predict']=1
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError,'incompatible'):
                comparison_summary(folder)
