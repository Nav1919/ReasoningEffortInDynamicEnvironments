"""Offline checks against GPT-OSS's observed architecture/control metadata."""
from pathlib import Path
import unittest
from experiment_config import load_config
from model_capabilities import verify_capabilities
from run_model_freeway import build_comparison_request


class GptOssPilotTests(unittest.TestCase):
    def test_pinned_recipe_matches_advertised_controls(self):
        c=load_config(Path(__file__).parent/'configs/gptoss_native_pilot.json',ready=True)
        metadata={'details':{'family':'gpt-oss'},
                  'thinking':{'values':['low','medium','high'],'default':'medium'}}
        evidence=verify_capabilities(c['model']['capability_profile'],c['modes'],metadata,'0.35.1')
        self.assertEqual(evidence['source'],'installed_server_metadata')
        requests=[build_comparison_request({'state_string':'same board'},c,mode,1)
                  for mode in ['low','medium','high']]
        self.assertEqual([r.pop('think') for r in requests],['low','medium','high'])
        self.assertTrue(all(r==requests[0] for r in requests))
        self.assertEqual(c['warmup_policy'],'load_once')
        self.assertEqual(c['generation']['num_predict'],2048)
        metadata['details']['family']='gptoss'
        with self.assertRaises(ValueError):
            verify_capabilities(c['model']['capability_profile'],c['modes'],metadata,'0.35.1')
