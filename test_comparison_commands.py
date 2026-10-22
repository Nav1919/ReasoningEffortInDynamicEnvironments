"""Offline command checks for the teammate guide. No provider calls."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import freeway_study
from experiment_config import validate_config
from test_experiment_config import ROOT, recipe


class CommandTests(unittest.TestCase):
    def test_native_dry_run_and_summary_make_no_model_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            argv=['study','plan','--config',str(ROOT/'configs/native_effort_draft.json'),
                  '--output',str(folder),'--dry-run']
            with patch('sys.argv',argv), patch('run_model_freeway.post_json') as provider, patch('builtins.print'):
                freeway_study.main()
                self.assertEqual(len(json.loads((folder/'plan.json').read_text())['runs']),18)
                with self.assertRaises(FileExistsError):
                    freeway_study.main()
            provider.assert_not_called()
            with patch('sys.argv',['study','summarize','--output',str(folder)]):
                freeway_study.main()
            report=json.loads((folder/'comparison_summary.json').read_text())
            self.assertEqual(sum(r['requests_attempted'] for r in report['metrics']),0)

    def test_failed_execution_is_not_a_successful_cli_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch('sys.argv',['study','execute','--output',temporary]), \
                 patch('comparison_execution.execute_plan',return_value={'status':'stopped'}):
                with self.assertRaisesRegex(RuntimeError,'stopped'):
                    freeway_study.main()

    def test_malformed_config_objects_have_clear_validation_errors(self):
        for key,value in [('model',None),('starts',[]),('model',{'tag':'x','expected_digest':None,
                                                       'capability_profile':[]})]:
            config=recipe()
            config[key]=value
            with self.assertRaises(ValueError):
                validate_config(config)
