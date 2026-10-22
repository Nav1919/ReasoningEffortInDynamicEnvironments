"""Check saved file integrity and reject damaged game records without AI calls."""
import copy
import hashlib
from pathlib import Path
import unittest

from freeway_study import read_episode
from replay_freeway import replay

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence/freeway_20261008'


class EvidenceIntegrityTests(unittest.TestCase):
    def test_every_published_file_matches_its_checksum(self):
        entries = (EVIDENCE / 'SHA256SUMS').read_text().splitlines()
        self.assertGreater(len(entries), 20)
        for entry in entries:
            expected, name = entry.split(maxsplit=1)
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest(),
                                 expected)

    def test_replay_rejects_changed_start_and_transition_fields(self):
        saved = read_episode(EVIDENCE / 'live_01_seed0_tick2.json.gz')
        changes = [
            lambda e: e.update(real_seed=-1),
            lambda e: e['steps'][0].update(turn=-1),
            lambda e: e['steps'][0].update(score=-999),
            lambda e: e['steps'][0].update(collision=not e['steps'][0]['collision']),
            lambda e: e['steps'][0].update(done=not e['steps'][0]['done']),
            lambda e: e['steps'][0].update(observation_before={}),
            lambda e: e['steps'][0].update(observation_after={}),
        ]
        for index, change in enumerate(changes):
            episode = copy.deepcopy(saved)
            change(episode)
            with self.subTest(change=index), self.assertRaises(ValueError):
                replay(episode)

    def test_replay_rejects_summary_counts_that_disagree_with_actions(self):
        saved = read_episode(EVIDENCE / 'live_01_seed0_tick2.json.gz')
        for field in ['turns', 'collisions']:
            episode = copy.deepcopy(saved)
            episode['summary'][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                replay(episode)
