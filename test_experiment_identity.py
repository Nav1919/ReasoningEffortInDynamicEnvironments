"""Offline identity tests. Run: python -m unittest test_experiment_identity."""
import copy
import json
import unittest
from experiment_identity import resolve_run
from test_experiment_config import recipe


class IdentityTests(unittest.TestCase):
    def test_stability_roundtrip_and_mode_separation(self):
        c = recipe()
        before = copy.deepcopy(c)
        a = resolve_run(c, 'off', 1, 0)
        reordered = {k:c[k] for k in reversed(c)}
        self.assertEqual(a, resolve_run(json.loads(json.dumps(reordered)), 'off', 1, 0))
        b = resolve_run(c, 'on', 1, 0)
        self.assertEqual(a['comparison_id'], b['comparison_id'])
        self.assertNotEqual(a['run_configuration_id'], b['run_configuration_id'])
        self.assertEqual(c, before)
        a['config']['generation']['num_predict'] = 1
        self.assertEqual(c, before)

    def test_full_experimental_design_changes_comparison(self):
        c = recipe()
        base = resolve_run(c, 'off', 1, 0)['comparison_id']
        mutations = [lambda c:c['generation'].update(num_predict=3000),
                     lambda c:c['generation'].update(seed=2),
                     lambda c:c.update(request_timeout=200),
                     lambda c:c.update(tick_intervals=[1,2]),
                     lambda c:c.update(scheduling_seed=7),
                     lambda c:c.update(modes={'off':c['modes']['off']}),
                     lambda c:c['model'].update(expected_digest='0'*64),
                     lambda c:c.update(replicates=2)]
        for mutate in mutations:
            c = recipe()
            mutate(c)
            self.assertNotEqual(base, resolve_run(c, 'off', 1, 0)['comparison_id'])

    def test_reserved_starts_and_invalid_replicates(self):
        for mode, selector, replicate in [('high',0,0),('off',5,0),('off',0,True),('off',0,1)]:
            with self.assertRaises(ValueError):
                resolve_run(recipe(), mode, 1, selector, replicate)
