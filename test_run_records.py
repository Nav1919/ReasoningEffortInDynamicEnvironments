"""Offline setup failures, interruption and evidence protection."""
import json
from pathlib import Path
import tempfile
import unittest
from experiment_identity import resolve_run
from run_records import setup_run
from test_experiment_config import recipe


class SetupLogTests(unittest.TestCase):
    def test_setup_is_saved_before_provider_and_failures_keep_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'run.json'
            resolved = resolve_run(recipe(),'off',1,0)
            def unavailable(config):
                self.assertEqual(json.loads(path.read_text())['run_status'],'setup')
                raise ConnectionError('Ollama is unavailable')
            record = setup_run(path,resolved,model_check=unavailable,source_check=lambda c:{})
            self.assertEqual(record['run_status'],'setup_failed')
            self.assertEqual(record['setup_failure']['stage'],'model_setup')
            self.assertEqual(record['resolved'],resolved)
            self.assertEqual(record['episode_outcome'],'not_started')
            self.assertEqual(json.loads(path.read_text()),record)
            with self.assertRaises(FileExistsError):
                setup_run(path,resolved,model_check=lambda c:{},source_check=lambda c:{})

    def test_success_and_interruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'success.json'
            r = resolve_run(recipe(),'on',1,0)
            record = setup_run(path,r,model_check=lambda c:{'digest':'verified'},source_check=lambda c:{})
            self.assertEqual(record['run_status'],'ready')
            self.assertEqual(record['start']['actual_seed'],1000)
            def interrupt(config):
                raise KeyboardInterrupt()
            path = Path(temporary)/'interrupted.json'
            with self.assertRaises(KeyboardInterrupt):
                setup_run(path,r,model_check=interrupt,source_check=lambda c:{})
            self.assertEqual(json.loads(path.read_text())['run_status'],'interrupted')
