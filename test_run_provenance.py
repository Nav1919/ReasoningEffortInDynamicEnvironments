"""Offline provenance tests, including packages without Git metadata."""
from unittest.mock import patch
import unittest
from run_provenance import source_provenance
from test_experiment_config import recipe


class SourceProvenanceTests(unittest.TestCase):
    def test_records_source_and_unavailable_revision_honestly(self):
        with patch('run_provenance.command', return_value=None):
            record = source_provenance(recipe())
        self.assertIsNone(record['project_commit'])
        self.assertIsNone(record['relevant_local_modifications'])
        self.assertIsNone(record['machine']['memory_bytes'])
        self.assertTrue(record['unavailable']['project_commit'])
        self.assertIn('run_model_freeway.py', record['source_sha256'])
        self.assertEqual(record['freeway_source_sha256'], recipe()['environment']['source_sha256'])
        self.assertIn('numpy', record['dependencies'])

    def test_source_mismatch_stops_before_gameplay(self):
        config = recipe()
        config['environment']['source_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'Freeway source'):
            source_provenance(config)
