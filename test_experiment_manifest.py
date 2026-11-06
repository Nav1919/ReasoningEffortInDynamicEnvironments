"""Offline behavior/failure tests for experiment_manifest.py.

Run: python -m unittest test_experiment_manifest -v (also root discovery).
Inputs: synthetic, non-scientific fixtures and temporary JSON files.
Outputs: unittest results; temporary files are removed. No simulator/model calls.
Coverage: required fields, split isolation, matched controls and CLI boundaries.
Documentation: docs/weekend/run-manifest.md. This file is its own test entry point.
"""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiment_manifest import ManifestError, validate_comparison, validate_manifest


def fixture():
    """Illustrative test values only; never a selected research configuration."""
    return {
        'frozen_model': {'name': 'TEST-ONLY-MODEL', 'revision': 'test-model-digest'},
        'simulator': {'name': 'TEST-ONLY-SIMULATOR', 'revision': 'test-source-digest'},
        'environment': {'name': 'TEST-ONLY-ENV', 'difficulty': {'test_level': 1}},
        'pressure': {'control': 'test_clock', 'value': 2, 'units': 'test_units',
                     'semantics': 'Synthetic control; no measured effect claimed.'},
        'common_settings': {'test_prompt': 'identical', 'test_sampling_seed': 17},
        'modes': {'quick': {'test_budget': 1}, 'deliberate': {'test_budget': 2}},
        'active_mode': 'quick',
        'seeds': {'development': [101, 102], 'held_out': [201, 202]},
        'output_path': 'test-only-output/quick.jsonl',
    }


# These checks separate structural validation from comparison invariants so a
# structurally valid but scientifically unmatched pair cannot pass unnoticed.
class ManifestTests(unittest.TestCase):
    def test_valid_manifest_is_not_mutated(self):
        manifest = fixture()
        saved = copy.deepcopy(manifest)
        self.assertIs(validate_manifest(manifest), manifest)
        self.assertEqual(manifest, saved)

    def test_every_required_field_and_identity_is_required(self):
        for key in fixture():
            with self.subTest(missing=key):
                manifest = fixture()
                del manifest[key]
                with self.assertRaises(ManifestError):
                    validate_manifest(manifest)
        for section in ('frozen_model', 'simulator'):
            for key in ('name', 'revision'):
                for invalid in ('', '  ', None, 1):
                    with self.subTest(section=section, key=key, invalid=invalid):
                        manifest = fixture()
                        manifest[section][key] = invalid
                        with self.assertRaises(ManifestError):
                            validate_manifest(manifest)

    def test_invalid_settings_and_shapes(self):
        changes = [
            ('environment', {'name': 'test', 'difficulty': {}}),
            ('pressure', {'control': 'x', 'value': None, 'units': 'x', 'semantics': 'x'}),
            ('common_settings', {}), ('common_settings', {'x': float('nan')}),
            ('common_settings', {'x': [float('inf')]}),
            ('common_settings', {'x': object()}),
            ('modes', {'quick': {}, 'deliberate': {}}),
            ('modes', {'quick': {'x': 1}, 'deliberate': {'x': 1}}),
            ('modes', {'quick': {'x': 1}, 'deliberate': {'y': 2}}),
            ('modes', {'quick': {'test_prompt': 1}, 'deliberate': {'test_prompt': 2}}),
            ('active_mode', 'adaptive'), ('output_path', ''), ('output_path', 'bad\x00path'),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                manifest = fixture()
                manifest[key] = value
                with self.assertRaises(ManifestError):
                    validate_manifest(manifest)
        for value in (None, [], {}, {'unexpected': 1}):
            with self.subTest(root=value), self.assertRaises(ManifestError):
                validate_manifest(value)

    def test_seed_leakage_duplicates_and_types(self):
        for seeds in ([201], [101, 101], [], [True], ['101'], [1.5], None):
            with self.subTest(seeds=seeds):
                manifest = fixture()
                manifest['seeds']['development'] = seeds
                with self.assertRaises(ManifestError):
                    validate_manifest(manifest)
        manifest = fixture()
        manifest['seeds']['held_out'] = []
        with self.assertRaises(ManifestError):
            validate_manifest(manifest)

    def test_unknown_fields_are_not_silently_ignored(self):
        for section in (None, 'frozen_model', 'simulator', 'environment', 'pressure', 'seeds', 'modes'):
            manifest = fixture()
            target = manifest if section is None else manifest[section]
            target['typo'] = 'value'
            with self.subTest(section=section), self.assertRaises(ManifestError):
                validate_manifest(manifest)

    def pair(self):
        first = fixture()
        second = copy.deepcopy(first)
        second['active_mode'] = 'deliberate'
        second['output_path'] = 'test-only-output/deliberate.jsonl'
        return [first, second]

    def test_matched_comparison_and_nonmutation(self):
        pair = self.pair()
        saved = copy.deepcopy(pair)
        self.assertIs(validate_comparison(pair), pair)
        self.assertEqual(pair, saved)

    def test_each_scientific_control_is_compared(self):
        replacements = {
            'frozen_model': {'name': 'OTHER', 'revision': 'other'},
            'simulator': {'name': 'OTHER', 'revision': 'other'},
            'environment': {'name': 'OTHER', 'difficulty': {'test_level': 2}},
            'pressure': {'control': 'other', 'value': 3, 'units': 'other', 'semantics': 'other'},
            'common_settings': {'test_prompt': 'different'},
            'modes': {'quick': {'test_budget': 3}, 'deliberate': {'test_budget': 4}},
            'seeds': {'development': [103], 'held_out': [203]},
        }
        for key, value in replacements.items():
            pair = self.pair()
            pair[1][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ManifestError, key):
                validate_comparison(pair)
        pair = self.pair()
        pair[1]['seeds']['held_out'].reverse()
        with self.assertRaisesRegex(ManifestError, 'seeds'):
            validate_comparison(pair)

    def test_comparison_rejects_bool_number_equivalence_and_output_aliases(self):
        pair = self.pair()
        pair[1]['common_settings']['test_sampling_seed'] = True
        pair[0]['common_settings']['test_sampling_seed'] = 1
        with self.assertRaisesRegex(ManifestError, 'common_settings'):
            validate_comparison(pair)
        pair = self.pair()
        pair[1]['output_path'] = 'test-only-output/../test-only-output/quick.jsonl'
        with self.assertRaisesRegex(ManifestError, 'output paths'):
            validate_comparison(pair)
        for pair in ([], [fixture()]):
            with self.assertRaises(ManifestError):
                validate_comparison(pair)

    def test_cli_success_failure_and_no_output_creation(self):
        script = str(Path(__file__).with_name('experiment_manifest.py').resolve())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / 'quick.json', root / 'deliberate.json']
            for path, manifest in zip(paths, self.pair()):
                path.write_text(json.dumps(manifest), encoding='utf-8')
            def run(*args):
                return subprocess.run([sys.executable, script, *map(str, args)],
                                      cwd=root, capture_output=True, text=True)
            for args in ([paths[0]], paths):
                result = run(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('scientific approval not implied', result.stdout)
            self.assertFalse((root / 'test-only-output').exists())
            mismatch = self.pair()[1]
            mismatch['frozen_model']['revision'] = 'different-test-revision'
            paths[1].write_text(json.dumps(mismatch), encoding='utf-8')
            result = run(*paths)
            self.assertEqual(result.returncode, 2)
            self.assertIn('mismatched frozen_model', result.stderr)
            for invalid in ('{', '{"x": 1, "x": 2}', 'null',
                            json.dumps(fixture()).replace('"test_level": 1', '"test_level": NaN')):
                paths[0].write_text(invalid, encoding='utf-8')
                result = run(paths[0])
                self.assertEqual(result.returncode, 2)
                self.assertIn('invalid manifest:', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
            self.assertEqual(run(root / 'missing.json').returncode, 2)
            self.assertEqual(run().returncode, 2)


if __name__ == '__main__':
    unittest.main()
