"""Fake-provider identity checks; no Ollama/network required."""
import unittest
from unittest.mock import patch, MagicMock
from run_model_freeway import post_json
from model_provenance import verify_model
from test_experiment_config import recipe


class ModelIdentityTests(unittest.TestCase):
    def provider(self, digest=None, family='qwen3'):
        def call(endpoint, payload, timeout):
            self.assertEqual(timeout, 180)
            return {'version':{'version':'0.35.1'},
                    'tags':{'models':[{'name':'qwen3:4b-q4_K_M',
                                      'digest':digest or recipe()['model']['expected_digest']}]},
                    'show':{'details':{'family':family},'template':'provider format'}}[endpoint]
        return call

    def test_match_records_actual_metadata(self):
        result = verify_model(recipe(), self.provider())
        self.assertEqual(result['digest'], recipe()['model']['expected_digest'])
        self.assertEqual(result['metadata']['template'], 'provider format')
        self.assertEqual(result['server_version'], '0.35.1')

    def test_digest_and_family_mismatch_stop_setup(self):
        for provider in [self.provider(digest='0'*64), self.provider(family='wrong')]:
            with self.assertRaises(ValueError):
                verify_model(recipe(), provider)

    def test_unselected_model_never_reaches_provider(self):
        c = recipe()
        c['model']['expected_digest'] = None
        calls = []
        with self.assertRaises(ValueError):
            verify_model(c, lambda *a, **k:calls.append(a))
        self.assertEqual(calls, [])


class MetadataTransportTests(unittest.TestCase):
    def test_metadata_get_and_chat_post(self):
        with patch('run_model_freeway.urlopen') as opening:
            opening.return_value.__enter__.return_value.read.return_value = b'{}'
            for endpoint in ['version', 'tags', 'show', 'chat']:
                post_json(endpoint, {}, timeout=7)
                request = opening.call_args.args[0]
                self.assertEqual(request.get_method(), 'GET' if endpoint in ['version','tags'] else 'POST')
                self.assertEqual(opening.call_args.kwargs['timeout'], 7)
