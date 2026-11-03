"""Offline integration checks using published evidence; no model requests.
Run: python -m unittest test_reproducibility.py
"""
import json
import contextlib
import io
from pathlib import Path
import shutil
import tempfile
import unittest
from freeway_study import read_episode, summarize
from replay_freeway import replay

EVIDENCE = Path(__file__).resolve().parent / 'evidence/freeway_20261008'


class ReproducibilityTests(unittest.TestCase):
    def test_all_saved_live_episodes_replay(self):
        manifest = json.loads((EVIDENCE/'live_manifest.json').read_text())
        self.assertEqual(len(manifest['episodes']), 15)
        for entry in manifest['episodes']:
            self.assertEqual(entry['status'], 'complete')
            episode = read_episode(EVIDENCE/entry['log'])
            with self.subTest(log=entry['log']):
                self.assertEqual(replay(episode)['verified_turns'], episode['summary']['turns'])
        broken = read_episode(EVIDENCE/manifest['episodes'][0]['log'])
        broken['steps'][0]['score'] = -999
        with self.assertRaises(ValueError):
            replay(broken)

    def test_incomplete_runs_are_retained_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)/'incomplete'
            shutil.copytree(EVIDENCE, folder)
            path = folder/'live_manifest.json'
            manifest = json.loads(path.read_text())
            manifest['episodes'].append(dict(status='failed', log='failed_attempt.json'))
            path.write_text(json.dumps(manifest))
            warning = io.StringIO()
            with contextlib.redirect_stderr(warning):
                summarize(folder)
            self.assertIn('failed_attempt.json (failed)', warning.getvalue())
            self.assertEqual(len(json.loads(path.read_text())['episodes']), 16)
            self.assertEqual(len(json.loads((folder/'live_episodes.json').read_text())), 15)

    def test_summary_regenerates_after_relocation(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)/'relocated'
            shutil.copytree(EVIDENCE, folder)
            # Only raw inputs, not saved summaries, may contribute to regeneration.
            names = ['diagnostic_summary', 'live_episodes', 'live_by_interval', 'live_paired']
            for name in names:
                for suffix in ['json', 'csv']:
                    (folder/f'{name}.{suffix}').unlink()
            summarize(folder)
            for name in names:
                self.assertEqual(json.loads((folder/f'{name}.json').read_text()),
                                 json.loads((EVIDENCE/f'{name}.json').read_text()))
                self.assertEqual((folder/f'{name}.csv').read_bytes(),
                                 (EVIDENCE/f'{name}.csv').read_bytes())
            rows = json.loads((folder/'live_by_interval.json').read_text())
            self.assertEqual([r['episodes'] for r in rows], [5,5,5])
            self.assertEqual([r['successes'] for r in rows], [0,2,2])
            records = [json.loads(line) for line in (folder/'diagnostics.jsonl').read_text().splitlines()]
            self.assertEqual(len(records), 135)
            self.assertEqual(len({r['situation_id'] for r in records}), 15)


if __name__ == '__main__':
    unittest.main()
