"""Offline capability checks. Run: python -m unittest test_model_capabilities."""
import copy
import unittest
from model_capabilities import validate_modes, verify_capabilities
from reasoning_modes import modes_for


class CapabilityTests(unittest.TestCase):
    def test_reject_unsupported_before_inference(self):
        with self.assertRaises(ValueError):
            validate_modes('qwen3-boolean-v1', modes_for('effort'))
        with self.assertRaises(ValueError):
            validate_modes('model-name-looks-right', modes_for('effort'))
        with self.assertRaises(ValueError):
            validate_modes('gpt-oss-effort-v1', {'oops':{'control':'effort','value':'max'}})

    def test_family_and_advertised_values(self):
        metadata = {'details':{'family':'gptoss'}, 'thinking':{'values':['low','medium','high']}}
        original = copy.deepcopy(metadata)
        result = verify_capabilities('gpt-oss-effort-v1', modes_for('effort'), metadata, 'future')
        self.assertEqual(result['source'], 'installed_server_metadata')
        self.assertEqual(metadata, original)
        metadata['thinking']['values'] = ['low']
        with self.assertRaises(ValueError):
            verify_capabilities('gpt-oss-effort-v1', modes_for('effort'), metadata, 'future')
        metadata['details']['family'] = 'qwen3'
        with self.assertRaises(ValueError):
            verify_capabilities('gpt-oss-effort-v1', modes_for('effort'), metadata, '0.35.1')

    def test_missing_metadata_needs_verified_version(self):
        metadata = {'details':{'family':'qwen3'}}
        result = verify_capabilities('qwen3-boolean-v1', modes_for('boolean'), metadata, '0.35.1')
        self.assertEqual(result['source'], 'explicit_verified_profile')
        with self.assertRaises(ValueError):
            verify_capabilities('qwen3-boolean-v1', modes_for('boolean'), metadata, 'unknown')
        metadata['thinking'] = {'values':[0, 1]}
        with self.assertRaises(ValueError):
            verify_capabilities('qwen3-boolean-v1', modes_for('boolean'), metadata, '0.35.1')
