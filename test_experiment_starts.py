"""Offline actual-start checks. No reserved game is played."""
import copy
import unittest
from experiment_starts import start_registry, validate_start_records
from freeway_study import recreate
from test_experiment_config import recipe


class StartSplitTests(unittest.TestCase):
    def test_actual_mapping_and_split(self):
        records = start_registry(recipe())
        self.assertEqual([r['actual_seed'] for r in records],
                         [1000,1001,1002,1003,1013,1014,1016,1018])
        self.assertEqual([r['split'] for r in records], ['development']*5+['evaluation']*3)
        self.assertEqual(records, start_registry(recipe()))
        self.assertEqual(len({r['initial_state_sha256'] for r in records}), 8)

    def test_duplicate_actual_seed_and_state_are_rejected(self):
        records = start_registry(recipe())
        for key in ['actual_seed', 'initial_state_sha256']:
            bad = copy.deepcopy(records)
            bad[-1][key] = bad[0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_start_records(bad)
        with self.assertRaises(ValueError):
            start_registry(recipe(), factory=lambda selector, prefix:recreate(0,''))
