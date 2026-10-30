"""Synthetic-only tests of evaluation_audit.py; no simulator or model calls.

Run: python -m unittest test_evaluation_audit -v
Inputs: temporary invented configs, starts, source files and deliberate damage.
Outputs: unittest assertions, including subprocess JSON/text/exit-code checks.
Tests for this runnable test module are its own cases; interface documentation:
docs/weekend/evaluation-audit.md. No historical evidence is read or modified.
"""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evaluation_audit import audit, config_digest, human_summary


# These labels, seeds and byte strings are invented test data, not approved
# policies, selected evaluation starts, or simulator/experiment results.
_DEFAULT = object()


class EvaluationAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = {
            'schema_version': 1,
            'frozen_config': {'model': {'id': 'SYNTHETIC-model', 'weights': 'fake'},
                              'settings': {'tick': 17},
                              'modes': {'synthetic-quick': {'budget': 3}}},
            'policies': {'fake-fixed': {'mode': 'synthetic-quick'},
                         'fake-router': {'threshold': 123}},
            'conditions': {'fake-slow': {'pressure': 13}, 'fake-fast': {'pressure': 29}},
            'starts': {'fake-dev': {'seed': -101, 'situation': 'invented-A'},
                       'fake-held': {'seed': -202, 'situation': 'invented-B'}},
            'splits': {'development': ['fake-dev'], 'held_out': ['fake-held']},
            'sources': {}, 'episodes': []}
        b = self.bundle
        b['frozen_config_digest'] = config_digest(b['frozen_config'])
        b['policy_digests'] = {p: config_digest(c) for p, c in b['policies'].items()}
        for role in ('runner', 'simulator', 'policies'):
            b['sources'][role] = dict(self.write_source(role + '.txt', b'SYNTHETIC source'),
                                      revision='SYNTHETIC-not-real-revision')
        for condition in b['conditions']:
            for policy in b['policies']:
                episode = {'episode_id': condition + policy, 'start_id': 'fake-held',
                           'condition_id': condition, 'policy_id': policy,
                           'status': 'completed'}
                for field, value in (('frozen_config', b['frozen_config']),
                                     ('start', b['starts']['fake-held']),
                                     ('condition', b['conditions'][condition]),
                                     ('policy', b['policies'][policy])):
                    episode[field] = copy.deepcopy(value)
                    episode[field + '_digest'] = config_digest(value)
                b['episodes'].append(episode)
                self.save_episode(episode)

    def write_source(self, name, data):
        (self.root / name).write_bytes(data)
        return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}

    def save_episode(self, episode):
        data = {k: v for k, v in episode.items() if k != 'source'}
        episode['source'] = self.write_source(episode['episode_id'] + '.json',
                                              json.dumps(data).encode())

    def codes(self, bundle=_DEFAULT):
        report = audit(self.bundle if bundle is _DEFAULT else bundle, self.root)
        self.assertFalse(report['comparison_allowed'])
        return {i['code'] for i in report['issues']}

    def test_complete_synthetic_matrix_and_read_only_determinism(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        original = copy.deepcopy(self.bundle)
        report = audit(self.bundle, self.root)
        self.assertTrue(report['comparison_allowed'], report)
        self.assertEqual(report['expected_episodes'], 4)
        self.assertEqual(report['recorded_episodes'], 4)
        self.assertEqual(len(report['coverage']), 4)
        self.assertEqual(report['issues'], [])
        self.assertEqual(report, audit(self.bundle, self.root))
        self.assertEqual(self.bundle, original)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertIn('PASS', human_summary(report))

    def test_missing_failed_and_duplicate_cells_are_all_visible(self):
        self.bundle['episodes'].pop()
        self.bundle['episodes'][0]['status'] = 'failed'
        self.save_episode(self.bundle['episodes'][0])
        self.bundle['episodes'].append(copy.deepcopy(self.bundle['episodes'][1]))
        codes = self.codes()
        self.assertTrue({'missing_episode', 'failed_episode', 'duplicate_cell',
                         'duplicate_episode', 'duplicate_source'} <= codes)
        report = audit(self.bundle, self.root)
        self.assertEqual(len(report['coverage']), 4)
        self.assertTrue(any(c['recorded'] == 0 for c in report['coverage']))
        self.assertIn('missing_episode', human_summary(report))

    def test_multiple_matched_starts_require_each_policy_at_each_condition(self):
        b = self.bundle
        b['starts']['fake-held-2'] = {'seed': -303, 'situation': 'invented-C'}
        b['splits']['held_out'].append('fake-held-2')
        for original in list(b['episodes']):
            episode = copy.deepcopy(original)
            episode['episode_id'] += '-second-start'
            episode['start_id'] = 'fake-held-2'
            episode['start'] = b['starts']['fake-held-2']
            episode['start_digest'] = config_digest(episode['start'])
            self.save_episode(episode)
            b['episodes'].append(episode)
        report = audit(b, self.root)
        self.assertTrue(report['comparison_allowed'], report)
        self.assertEqual(report['expected_episodes'], 8)
        b['episodes'] = [e for e in b['episodes'] if not (
            e['start_id'] == 'fake-held-2' and e['policy_id'] == 'fake-router')]
        report = audit(b, self.root)
        self.assertFalse(report['comparison_allowed'])
        missing = [i for i in report['issues'] if i['code'] == 'missing_episode']
        self.assertEqual(len(missing), 2)
        self.assertTrue(all('fake-held-2' in i['location'] for i in missing))

    def test_empty_evidence_refuses_every_expected_cell(self):
        self.bundle['episodes'] = []
        report = audit(self.bundle, self.root)
        self.assertEqual(len(report['issues']), 4)
        self.assertEqual(self.codes(), {'missing_episode'})

    def test_payload_and_declared_digests_both_checked(self):
        for field in ('frozen_config', 'start', 'condition', 'policy'):
            for change_digest in (False, True):
                b = copy.deepcopy(self.bundle)
                e = b['episodes'][0]
                if change_digest:
                    e[field + '_digest'] = '0' * 64
                else:
                    e[field]['CORRUPTION'] = 'changed'
                self.save_episode(e)
                with self.subTest(field=field, digest=change_digest):
                    self.assertIn('mismatched_' + field, self.codes(b))

    def test_model_or_settings_changed_even_with_recomputed_episode_digest(self):
        for field in ('model', 'settings', 'modes'):
            b = copy.deepcopy(self.bundle)
            e = b['episodes'][0]
            e['frozen_config'][field]['changed'] = True
            e['frozen_config_digest'] = config_digest(e['frozen_config'])
            self.save_episode(e)
            with self.subTest(field=field):
                self.assertIn('mismatched_frozen_config', self.codes(b))

    def test_manifest_digests_must_match_payloads(self):
        b = copy.deepcopy(self.bundle)
        b['frozen_config']['settings']['tick'] = 99
        self.assertIn('config_digest', self.codes(b))
        self.bundle['policies']['fake-fixed']['mode'] = 'different'
        self.assertIn('policy_digest', self.codes())

    def test_split_overlap_and_aliases(self):
        b = copy.deepcopy(self.bundle)
        b['splits']['development'].append('fake-held')
        self.assertIn('split_overlap', self.codes(b))
        b = copy.deepcopy(self.bundle)
        b['starts']['fake-dev'] = copy.deepcopy(b['starts']['fake-held'])
        self.assertIn('split_overlap', self.codes(b))
        b = copy.deepcopy(self.bundle)
        b['splits']['held_out'].append('fake-held')
        self.assertIn('duplicate_start', self.codes(b))
        b = copy.deepcopy(self.bundle)
        b['starts']['alias'] = copy.deepcopy(b['starts']['fake-held'])
        b['splits']['held_out'].append('alias')
        self.assertIn('duplicate_start', self.codes(b))

    def test_unknown_or_development_episodes_never_count_as_coverage(self):
        for key, value in (('start_id', 'fake-dev'), ('condition_id', 'unknown'),
                           ('policy_id', [])):
            b = copy.deepcopy(self.bundle)
            b['episodes'][0][key] = value
            with self.subTest(key=key):
                self.assertTrue({'unexpected_episode', 'missing_episode'} <= self.codes(b))

    def test_provenance_missing_corrupt_mismatched_or_reused(self):
        changes = [lambda e: e.pop('source'),
                   lambda e: e['source'].update(sha256='0' * 64),
                   lambda e: e['source'].update(path='missing.json'),
                   lambda e: e['source'].update(path='../escape.json'),
                   lambda e: e['source'].update(path=str(self.root / 'absolute.json')),
                   lambda e: e.update(status='completed', episode_id='different-id')]
        for change in changes:
            b = copy.deepcopy(self.bundle)
            change(b['episodes'][0])
            self.assertIn('provenance', self.codes(b))
        b = copy.deepcopy(self.bundle)
        b['sources']['runner'].pop('revision')
        self.assertIn('provenance', self.codes(b))
        b = copy.deepcopy(self.bundle)
        b['episodes'][1]['source'] = b['episodes'][0]['source']
        self.assertIn('duplicate_source', self.codes(b))

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'source'
            target.write_bytes(b'SYNTHETIC source')
            (self.root / 'escape').symlink_to(target)
            self.bundle['sources']['runner']['path'] = 'escape'
            self.assertIn('provenance', self.codes())

    def test_invalid_shapes_fail_closed(self):
        corruptions = [None, [], {}, {'schema_version': True}]
        for field, value in [('policies', {}), ('episodes', None), ('sources', {}),
                             ('frozen_config_digest', 'not-a-digest'),
                             ('policy_digests', {}), ('starts', {}),
                             ('splits', {'development': [], 'held_out': []})]:
            b = copy.deepcopy(self.bundle)
            b[field] = value
            corruptions.append(b)
        b = copy.deepcopy(self.bundle)
        b['frozen_config']['settings']['bad'] = float('nan')
        corruptions.append(b)
        for b in corruptions:
            with self.subTest(bundle=b):
                self.assertEqual(self.codes(b), {'invalid_input'})
        self.bundle['episodes'][0] = None
        self.assertIn('invalid_episode', self.codes())

    def test_canonical_digest_and_nonfinite_rejection(self):
        self.assertEqual(config_digest({'a': 1, 'b': 'é'}),
                         config_digest({'b': 'é', 'a': 1}))
        self.assertNotEqual(config_digest({'a': 1}), config_digest({'a': True}))
        with self.assertRaises(ValueError):
            config_digest(float('inf'))

    def test_cli_formats_exit_codes_and_unreadable_input(self):
        script = Path(__file__).with_name('evaluation_audit.py')
        path = self.root / 'bundle.json'
        def run(fmt='json'):
            return subprocess.run([sys.executable, str(script), str(path),
                                   '--source-root', str(self.root), '--format', fmt],
                                  capture_output=True, text=True)
        path.write_text(json.dumps(self.bundle))
        result = run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['comparison_allowed'])
        self.assertIn('PASS', run('text').stdout)
        self.bundle['episodes'].pop()
        path.write_text(json.dumps(self.bundle))
        result = run()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)['comparison_allowed'])
        self.assertIn('REFUSED', run('text').stdout)
        for text in ('{bad', '{"schema_version":1,"schema_version":1}', '{"bad":NaN}'):
            path.write_text(text)
            self.assertEqual(run().returncode, 2)
        path.unlink()
        self.assertEqual(run().returncode, 2)


if __name__ == '__main__':
    unittest.main()
