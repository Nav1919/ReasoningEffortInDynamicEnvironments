"""Recompute saved unsuccessful native attempts offline; no model calls."""
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from comparison_metrics import write_comparison_summary

PACKAGE=Path(__file__).parent/'evidence/gptoss_local_pilot_20261019/records.tar.gz'


class SavedGptOssTests(unittest.TestCase):
    def test_both_attempt_summaries_rebuild_after_relocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            with tarfile.open(PACKAGE) as archive:
                archive.extractall(folder,filter='data')
            for attempt in ['attempt1','attempt2']:
                output=folder/attempt
                expected=json.loads((output/'comparison_summary.json').read_text())
                (output/'comparison_summary.json').unlink()
                (output/'comparison_modes.csv').unlink()
                self.assertEqual(write_comparison_summary(output),expected)

    def test_failure_counts_do_not_invent_answers_or_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            with tarfile.open(PACKAGE) as archive:
                archive.extractall(folder,filter='data')
            for attempt,questions,status in [('attempt1',0,'setup_failed'),('attempt2',1,'failed')]:
                output=folder/attempt
                execution=json.loads((output/'execution.json').read_text())
                self.assertEqual(execution['runs'][0]['status'],status)
                self.assertTrue(all(r['status']=='planned' for r in execution['runs'][1:]))
                report=write_comparison_summary(output)
                self.assertEqual(sum(m['requests_attempted'] for m in report['metrics']),questions)
                self.assertEqual(sum(m['valid_action_rate']['numerator'] for m in report['metrics']),0)
                self.assertTrue(all(m['output_token_totals']['output_tokens'] is None for m in report['metrics']))
