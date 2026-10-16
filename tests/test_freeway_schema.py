"""Synthetic contract tests; these are not Freeway observations or evidence.

Run: python3 -B -m unittest discover -s tests -v (from repository root).
Inputs: isolated in-memory fixtures. Output: unittest report, no files/network.
Implementation: ../src/freeway_schema.py; usage: ../docs/offline-skeleton.md.
"""

import copy
import json
import unittest
from pathlib import Path

from src.freeway_schema import validate_manifest, validate_record


# Fictional settings exercise schema mechanics without selecting a real model,
# simulator difficulty, pressure control, or scientific experiment condition.
def fixture():
    manifest = dict(schema_version=1, environment='RealtimeGym/Freeway',
                    model_identifier='synthetic-test-only',
                    modes={'quick': {'test_budget': 1}, 'deliberate': {'test_budget': 2}},
                    difficulties={'test': {}}, pressures={'test': {}}, older_view_seconds=1,
                    starts={'development': [{'start_id': 'dev', 'seed': 1}],
                            'held_out': [{'start_id': 'held', 'seed': 2}]})
    record = dict(schema_version=1, run_id='synthetic', decision_index=0,
                  start_id='dev', seed=1, split='development',
                  model_identifier='synthetic-test-only', mode='quick',
                  mode_configuration={'test_budget': 1}, difficulty='test', pressure='test',
                  observation_time_seconds=10, action_time_seconds=12,
                  observation_age_seconds=2, action='U', outcome={'synthetic': True},
                  input_tokens=3, output_tokens=1, reasoning_tokens=0,
                  elapsed_seconds=1.5, failures=[])
    return manifest, record


class SchemaTests(unittest.TestCase):
    def test_committed_draft_is_not_ready(self):
        path = Path(__file__).resolve().parents[1] / 'configs/freeway.json'
        manifest = json.loads(path.read_text())
        validate_manifest(manifest)
        with self.assertRaises(ValueError):
            validate_manifest(manifest, ready=True)

    def test_round_trip_and_actions(self):
        manifest, record = fixture()
        for action in ('U', 'D', 'S'):
            record['action'] = action
            self.assertEqual(validate_record(json.loads(json.dumps(record)), manifest), record)
        for action in ('up', 'u', '', ' U ', None):
            record['action'] = action
            with self.assertRaises(ValueError):
                validate_record(record, manifest)

    def test_split_leakage_and_mislabeling(self):
        manifest, record = fixture()
        for field in ('start_id', 'seed'):
            bad = copy.deepcopy(manifest)
            bad['starts']['held_out'][0][field] = bad['starts']['development'][0][field]
            with self.assertRaises(ValueError):
                validate_manifest(bad)
        record.update(start_id='held', seed=2, split='held_out')
        validate_record(record, manifest)
        with self.assertRaises(ValueError):
            validate_record(record, manifest, purpose='development')
        record['split'] = 'development'
        with self.assertRaises(ValueError):
            validate_record(record, manifest)

    def test_record_rejects_drift_and_invalid_measurements(self):
        manifest, record = fixture()
        mutations = {'model_identifier': 'other', 'mode_configuration': {},
                     'difficulty': 'unknown', 'pressure': 'unknown', 'mode': 'other',
                     'seed': True, 'input_tokens': True, 'output_tokens': -1, 'reasoning_tokens': 1.5,
                     'elapsed_seconds': float('nan'), 'observation_age_seconds': 3,
                     'action_time_seconds': 9, 'outcome': None, 'failures': 'timeout'}
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_record(dict(record, **{field: value}), manifest)

    def test_failures_retain_unknowns_without_zero_imputation(self):
        manifest, record = fixture()
        record.update(action=None, outcome=None, output_tokens=None,
                      reasoning_tokens=None, failures=['synthetic timeout'])
        validate_record(record, manifest)
        record['action'] = 'INVALID'
        with self.assertRaises(ValueError):
            validate_record(record, manifest)

    def test_manifest_environment_and_modes(self):
        manifest, _ = fixture()
        for field, value in [('environment', 'other'), ('modes', {'quick': {}}),
                             ('older_view_seconds', float('inf'))]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_manifest(dict(manifest, **{field: value}))


if __name__ == '__main__':
    unittest.main()
