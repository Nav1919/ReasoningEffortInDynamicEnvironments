"""Run the real live loop with immediate fake responses and a controllable clock."""
from concurrent.futures import Future
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_model_freeway as runner
import run_records
from test_experiment_config import ROOT


class ImmediateWorker:
    def __init__(self, **kwargs):
        pass
    def submit(self, function, *args):
        result = Future()
        result.set_result(function(*args))
        return result
    def shutdown(self, **kwargs):
        pass


class ControlledRunnerTests(unittest.TestCase):
    def test_saved_live_recipe_and_separate_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'run.json'
            setup = run_records.setup_run
            def fake_setup(path, resolved):
                return setup(path, resolved, source_check=lambda c:{},
                             model_check=lambda c:{'metadata':{},'digest':c['model']['expected_digest']})
            def request(payload, probe, timeout=180):
                # Every game action is invalid: it must remain fallback, not model S.
                return {'message':{'content':'prose'},'done_reason':'stop'}, None, 0, .1
            clock = itertools.count(step=.1)
            argv = ['runner','--experiment-config',str(ROOT/'configs/qwen_live.json'),
                    '--mode','off','--log-path',str(path)]
            with patch('sys.argv',argv), patch('run_records.setup_run',side_effect=fake_setup), \
                 patch.object(runner,'request_action',side_effect=request), \
                 patch.object(runner,'ThreadPoolExecutor',ImmediateWorker), \
                 patch.object(runner.time,'perf_counter',side_effect=lambda:next(clock)), \
                 patch.object(runner.time,'sleep'), patch('builtins.print'):
                runner.main()
            episode = json.loads(path.read_text())
            self.assertEqual(episode['run_status'],'complete')
            self.assertEqual(episode['resolved']['selected_mode'],'off')
            self.assertEqual(episode['start']['actual_seed'],1000)
            fallbacks = [s for s in episode['steps'] if s['action_source']=='invalid_fallback']
            self.assertTrue(fallbacks)
            self.assertTrue(all(s['action']=='S' for s in fallbacks))
            self.assertTrue(all(d['request_status']=='invalid_action' for d in episode['decisions']))
            self.assertTrue(all('messages' in d['request'] for d in episode['decisions']))

    def test_timeout_does_not_submit_another_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'timeout.json'
            setup = run_records.setup_run
            def fake_setup(path, resolved):
                return setup(path,resolved,source_check=lambda c:{},model_check=lambda c:{'metadata':{}})
            results = [({'message':{'content':'S'},'done_reason':'stop'},None,0,.1),
                       (None,'TimeoutError: timed out',0,.1)]
            argv = ['runner','--experiment-config',str(ROOT/'configs/qwen_live.json'),
                    '--mode','off','--log-path',str(path)]
            with patch('sys.argv',argv), patch('run_records.setup_run',side_effect=fake_setup), \
                 patch.object(runner,'request_action',side_effect=results) as requests, \
                 patch.object(runner,'ThreadPoolExecutor',ImmediateWorker), patch('builtins.print'):
                with self.assertRaises(TimeoutError):
                    runner.main()
            self.assertEqual(requests.call_count,2)  # one warm-up, one timed-out game call
            record = json.loads(path.read_text())
            self.assertEqual(record['run_status'],'failed')
            self.assertEqual(record['decisions'][0]['request_status'],'timeout')
