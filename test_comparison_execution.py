"""Offline plan → fake provider → logs, including missing/failed runs."""
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from comparison_execution import execute_plan
from comparison_plan import build_plan
from test_experiment_config import recipe


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c=recipe()
        c['tick_intervals']=[1]
        cls.plan=build_plan(c)

    def prepare(self, folder):
        (folder/'plan.json').write_text(json.dumps(self.plan))

    def execute(self, folder, provider, **kwargs):
        clock=itertools.count()
        return execute_plan(folder,provider=provider,model_check=kwargs.pop('model_check',lambda c:{}),
                            source_check=lambda c:{},clock=lambda:next(clock),**kwargs)

    def test_success_and_preserved_missing_partners(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            self.prepare(folder)
            result=self.execute(folder,lambda *a,**k:{'message':{'content':'S'},'done_reason':'stop'},limit=1)
            self.assertEqual(result['status'],'partial')
            self.assertEqual([r['status'] for r in result['runs'][:2]],['complete','planned'])
            with self.assertRaises(FileExistsError):
                self.execute(folder,lambda *a,**k:None)

    def test_setup_failure_stops_without_provider_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            self.prepare(folder)
            calls=[]
            def fail(config):
                raise ConnectionError('not available')
            result=self.execute(folder,lambda *a,**k:calls.append(a),model_check=fail,limit=2)
            self.assertEqual(result['status'],'stopped')
            self.assertEqual(result['runs'][0]['status'],'setup_failed')
            self.assertEqual(result['runs'][1]['status'],'planned')
            self.assertEqual(calls,[])

    def test_interruption_retains_current_and_future_statuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            self.prepare(folder)
            def interrupt(*args,**kwargs):
                raise KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):
                self.execute(folder,interrupt,limit=2)
            result=json.loads((folder/'execution.json').read_text())
            self.assertEqual(result['runs'][0]['status'],'interrupted')
            self.assertEqual(result['runs'][1]['status'],'planned')
