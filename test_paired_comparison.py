"""Synthetic-only behavior/failure checks for paired_comparison.py.

Run: python -m unittest test_paired_comparison -v, or run this file directly.
Inputs: generated synthetic records and temporary JSON/CSV files. Outputs:
unittest assertions/status; no model measurements or inference. Implementation:
paired_comparison.py; schema: docs/weekend/paired-comparison.md. This suite checks
matching, coverage, arithmetic, malformed records and real CLI file round trips.
"""
import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from paired_comparison import CONTROLS, METRICS, analyze, load_records


# Every number here is invented solely to exercise software behavior. These
# fixtures are not pilot results, model configurations, or scientific evidence.
def synthetic(mode='quick', **changes):
    record = dict(scenario='synthetic-crossing', start='synthetic-seed-0',
                  difficulty='synthetic-easy', pressure='synthetic-pressure',
                  observation_condition='synthetic-current', model_identity='synthetic-model',
                  mode=mode, shared_settings={'prompt': 'synthetic', 'seed': 0},
                  mode_settings={'synthetic_budget': 1 if mode == 'quick' else 2},
                  status='completed', error='', outcome=1 if mode == 'quick' else 3,
                  seconds=2 if mode == 'quick' else 5,
                  tokens=10 if mode == 'quick' else 30, evidence_kind='synthetic')
    record.update(changes)
    return record


class PairedComparisonTests(unittest.TestCase):
    def test_arithmetic_direction_and_coverage(self):
        records = [synthetic(), synthetic('deliberate')]
        before = copy.deepcopy(records)
        result = analyze(records)
        pair = result['pairs'][0]
        self.assertEqual([pair[f + '_difference'] for f in METRICS], [2, 3, 20])
        self.assertEqual(result['coverage']['completed_pairs'], 1)
        self.assertEqual(result['coverage']['paired_metrics'], dict.fromkeys(METRICS, 1))
        self.assertEqual(result['records'], records)
        self.assertEqual(records, before)
        self.assertEqual(analyze(records[::-1])['pairs'], result['pairs'])

    def test_negative_and_zero_differences(self):
        result = analyze([synthetic(), synthetic('deliberate', outcome=-1, seconds=2, tokens=0)])
        self.assertEqual([result['pairs'][0][f + '_difference'] for f in METRICS], [-2, 0, -10])

    def test_every_control_prevents_cross_pairing(self):
        for field in CONTROLS:
            records = [synthetic(), synthetic('deliberate')]
            records[1][field] += '-different'
            with self.subTest(field=field):
                if field == 'model_identity':
                    with self.assertRaises(ValueError):
                        analyze(records)
                else:
                    result = analyze(records)
                    self.assertEqual(result['coverage']['starts'], 2)
                    self.assertEqual(result['coverage']['completed_pairs'], 0)
                    for mode in ('quick', 'deliberate'):
                        self.assertEqual(result['coverage']['by_mode'][mode]['missing'], 1)

    def test_failures_missing_and_partial_measurements_are_retained(self):
        failed = synthetic('deliberate', status='failed', error='synthetic timeout',
                           outcome=None, seconds=4, tokens=12)
        records = [synthetic(), failed,
                   synthetic(start='unpaired'),
                   synthetic(start='planned-absent', status='missing', error='not run',
                             outcome=None, seconds=None, tokens=None),
                   synthetic('deliberate', start='planned-absent', status='missing',
                             error='not run', outcome=None, seconds=None, tokens=None)]
        result = analyze(records)
        self.assertEqual(result['records'], records)
        self.assertEqual(result['coverage']['by_mode'], {
            'quick': {'completed': 2, 'failed': 0, 'missing': 1},
            'deliberate': {'completed': 0, 'failed': 1, 'missing': 2}})
        self.assertTrue(all(p[f + '_difference'] is None for p in result['pairs'] for f in METRICS))

    def test_null_costs_never_imputed(self):
        result = analyze([synthetic(seconds=None), synthetic('deliberate', tokens=None)])
        self.assertEqual(result['coverage']['paired_metrics'], {'outcome': 1, 'seconds': 0, 'tokens': 0})
        self.assertIsNone(result['pairs'][0]['seconds_difference'])
        self.assertIsNone(result['pairs'][0]['tokens_difference'])

    def test_duplicate_and_conflicting_settings(self):
        cases = [
            [synthetic(), synthetic()],
            [synthetic(), synthetic('deliberate', shared_settings={'prompt': 'changed'})],
            [synthetic(), synthetic('deliberate', mode_settings={'synthetic_budget': 1})],
            [synthetic(), synthetic(start='other', mode_settings={'synthetic_budget': 99})],
            [synthetic(), synthetic('deliberate', evidence_kind='measured')],
        ]
        for records in cases:
            with self.subTest(records=records), self.assertRaises(ValueError):
                analyze(records)

    def test_invalid_schema_status_and_metrics(self):
        changes = [dict(start=''), dict(mode='adaptive'), dict(status='success'),
                   dict(shared_settings={}), dict(mode_settings=[]), dict(error=None),
                   dict(error='completed but error'), dict(status='failed'),
                   dict(evidence_kind='pilot'), dict(outcome=None), dict(tokens=1.5),
                   dict(tokens=True), dict(seconds=-1), dict(outcome=float('nan')),
                   dict(seconds=float('inf')), dict(outcome='1'),
                   dict(shared_settings={'bad': float('nan')}),
                   dict(status='missing', error='not run')]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                analyze([synthetic(**change)])
        for records in ([], {}, [None], [dict(synthetic(), extra='unknown')]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                analyze(records)
        row = synthetic()
        del row['pressure']
        with self.assertRaises(ValueError):
            analyze([row])

    # Exercise the real CLI and disk formats, not just a mocked entry point.
    def test_json_csv_cli_round_trip_and_rejection(self):
        records = [synthetic(), synthetic('deliberate', seconds=None)]
        script = str(Path(__file__).with_name('paired_comparison.py'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, report, pairs = root/'input.json', root/'report.json', root/'pairs.csv'
            source.write_text(json.dumps(records), encoding='utf-8')
            command = [sys.executable, script, str(source), '--output', str(report),
                       '--csv-output', str(pairs)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(report.read_text()), analyze(records))
            with pairs.open(newline='') as handle:
                flat = list(csv.DictReader(handle))
            self.assertEqual(flat[0]['evidence_kind'], 'synthetic')
            self.assertEqual(flat[0]['outcome_difference'], '2')
            self.assertEqual(flat[0]['seconds_difference'], '')
            csv_source = root/'input.csv'
            with csv_source.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(records[0]))
                writer.writeheader()
                for record in records:
                    writer.writerow({k: json.dumps(v) if isinstance(v, dict) or k in METRICS
                                     else v for k, v in record.items()})
            self.assertEqual(analyze(load_records(csv_source)), analyze(records))
            command[2] = str(csv_source)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            report.unlink()
            source.write_text(json.dumps([records[0], records[0]]))
            command[2] = str(source)
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn('duplicate', run.stderr)
            self.assertFalse(report.exists())
            run = subprocess.run([sys.executable, script, str(source), '--output', str(source)],
                                 capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(json.loads(source.read_text()), [records[0], records[0]])

    def test_duplicate_json_keys_rejected_including_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.json'
            path.write_text('[{"mode": "quick", "mode": "deliberate"}]')
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                load_records(path)
            path = Path(directory)/'bad.csv'
            with path.open('w', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(list(synthetic()))
                record = synthetic()
                writer.writerow(['{"temperature": 0, "temperature": 1}' if k == 'shared_settings'
                                 else json.dumps(v) if isinstance(v, dict) or k in METRICS
                                 else v for k, v in record.items()])
            with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
                load_records(path)

    def test_bad_csv_and_nonfinite_difference(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'bad.csv'
            path.write_text('mode,mode\nquick,deliberate\n')
            with self.assertRaises(ValueError):
                load_records(path)
            path.write_text(','.join(k for k in synthetic() if k != 'seconds') + '\n')
            with self.assertRaisesRegex(ValueError, 'documented columns'):
                load_records(path)
        with self.assertRaises(ValueError):
            analyze([synthetic(outcome=-1e308), synthetic('deliberate', outcome=1e308)])


if __name__ == '__main__':
    unittest.main()
