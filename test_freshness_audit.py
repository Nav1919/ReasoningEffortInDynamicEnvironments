"""Offline behavior/failure tests for freshness_audit.py (no simulator/model).

Run: python -m unittest test_freshness_audit -v, or execute this file directly.
Inputs: synthetic native-log fixtures and temporary JSON/gzip files. Output:
unittest assertions, including CLI exit/output checks. Metric documentation:
docs/weekend/freshness-audit.md. This file is its own linked test suite.
"""
import copy
import gzip
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from freshness_audit import audit_episode


def observation(turn, head=0):
    return {'game_turn': turn, 'state': {'player_states': 0,
            'car_states': [[1, head, 'right', 12, 11]]}}


def episode():
    # Action at tick 4 uses the world after tick 3, not after its own transition.
    return {'decisions': [{'id': 0, 'status': 'applied', 'observed_turn': 1,
            'observation': observation(1), 'observed_seconds': 1.,
            'submitted_seconds': 1.1, 'request_started_seconds': 1.2,
            'response_finished_seconds': 2.5, 'response_collected_turn': 3,
            'applied_turn': 4, 'applied_seconds': 3.,
            'latency_seconds': 1.3, 'observation_age_turns': 2,
            'observation_age_seconds': 2.}],
            'steps': [{'turn': 4, 'elapsed_seconds': 3., 'decision_id': 0,
                       'observation_before': observation(3, 24),
                       'observation_after': {}, 'done': True}]}


# Hand-computed fixtures distinguish endpoint traffic change from elapsed age,
# and ensure terminal post-action emptiness is not compared with the supplied view.
class FreshnessAuditTests(unittest.TestCase):
    def test_changed_and_decomposition_without_mutation(self):
        data = episode()
        original = copy.deepcopy(data)
        row = audit_episode(data)['decisions'][0]
        self.assertEqual(row['observation_age_turns'], 2)
        self.assertEqual(row['observation_age_seconds'], 2)
        self.assertAlmostEqual(row['pre_request_seconds'], .2)
        self.assertAlmostEqual(row['inference_seconds'], 1.3)
        self.assertAlmostEqual(row['alignment_wait_seconds'], .5)
        self.assertTrue(row['traffic_changed'])
        self.assertEqual(row['missing_metrics'], [])
        self.assertEqual(data, original)

    def test_unchanged_ignores_player_turn_and_car_order(self):
        data = episode()
        cars = [[2, -12, 'left', 4, 11], [1, 0, 'right', 12, 11]]
        data['decisions'][0]['observation']['state']['car_states'] = cars
        before = data['steps'][0]['observation_before']
        before['state']['car_states'] = list(reversed(cars))
        before['state']['player_states'] = 8
        self.assertFalse(audit_episode(data)['decisions'][0]['traffic_changed'])

    def test_empty_traffic_is_known_and_not_missing(self):
        data = episode()
        data['decisions'][0]['observation']['state']['car_states'] = []
        data['steps'][0]['observation_before']['state']['car_states'] = []
        self.assertIs(audit_episode(data)['decisions'][0]['traffic_changed'], False)

    def test_immediate_next_tick_has_zero_turn_age(self):
        data = episode()
        decision = data['decisions'][0]
        decision.update(applied_turn=2, response_collected_turn=1, observation_age_turns=0)
        data['steps'][0].update(turn=2, observation_before=observation(1))
        row = audit_episode(data)['decisions'][0]
        self.assertEqual(row['observation_age_turns'], 0)
        self.assertFalse(row['traffic_changed'])

    def test_missing_fields_are_not_reconstructed_from_saved_ages(self):
        data = {'decisions': [{'id': 0, 'observation_age_seconds': 12}]}
        result = audit_episode(data)
        row = result['decisions'][0]
        self.assertIsNone(row['observation_age_seconds'])
        self.assertIsNone(row['traffic_changed'])
        self.assertEqual(len(row['missing_metrics']), 6)
        self.assertEqual(result['missing_counts']['inference_seconds'], 1)
        self.assertFalse(result['steps_field_present'])
        self.assertEqual(audit_episode({})['decision_count'], 0)
        self.assertFalse(audit_episode({})['decisions_field_present'])

    def test_terminal_late_response_has_inference_but_no_action_age(self):
        data = {'decisions': [{'id': 0, 'status': 'discarded_after_episode',
                'observed_turn': 9, 'request_started_seconds': 8.,
                'response_finished_seconds': 15.}], 'steps': []}
        row = audit_episode(data)['decisions'][0]
        self.assertEqual(row['inference_seconds'], 7)
        self.assertIsNone(row['alignment_wait_seconds'])
        self.assertIsNone(row['observation_age_turns'])
        data['decisions'][0]['status'] = 'pending_when_episode_ended'
        del data['decisions'][0]['response_finished_seconds']
        self.assertIsNone(audit_episode(data)['decisions'][0]['inference_seconds'])

    def test_missing_tick_does_not_invent_traffic(self):
        data = episode()
        data['steps'] = []
        row = audit_episode(data)['decisions'][0]
        self.assertEqual(row['observation_age_seconds'], 2)
        self.assertIsNone(row['traffic_changed'])
        data = episode()
        del data['steps'][0]['observation_before']
        self.assertIsNone(audit_episode(data)['decisions'][0]['traffic_changed'])

    def test_tick_can_supply_application_clock(self):
        data = episode()
        del data['decisions'][0]['applied_seconds']
        del data['decisions'][0]['applied_turn']
        row = audit_episode(data)['decisions'][0]
        self.assertEqual(row['observation_age_seconds'], 2)
        self.assertEqual(row['observation_age_turns'], 2)

    def test_invalid_numbers_and_negative_durations(self):
        for field in ('observed_seconds', 'submitted_seconds', 'request_started_seconds',
                      'response_finished_seconds', 'applied_seconds', 'latency_seconds',
                      'observation_age_seconds', 'observed_turn', 'applied_turn',
                      'observation_age_turns', 'ticks_during_request', 'response_collected_turn'):
            for value in (-1, float('nan'), float('inf'), True, '1'):
                with self.subTest(field=field, value=value):
                    data = episode()
                    data['decisions'][0][field] = value
                    with self.assertRaises(ValueError):
                        audit_episode(data)
        for field, value in [('response_finished_seconds', 1.), ('applied_seconds', 2.),
                             ('observed_turn', 4), ('applied_turn', 3),
                             ('latency_seconds', 2.), ('response_collected_turn', 4),
                             ('observation_age_seconds', 4.), ('observed_turn', 1.5)]:
            with self.subTest(field=field):
                data = episode()
                data['decisions'][0][field] = value
                with self.assertRaises(ValueError):
                    audit_episode(data)

    def test_bad_ticks_and_joins(self):
        for field, value in [('elapsed_seconds', -1), ('elapsed_seconds', float('inf')),
                             ('elapsed_seconds', 4), ('turn', 5), ('decision_id', 9),
                             ('done', 'yes'), ('scheduler_lag_seconds', -1)]:
            with self.subTest(field=field):
                data = episode()
                data['steps'][0][field] = value
                with self.assertRaises(ValueError):
                    audit_episode(data)
        for mutate in (
            lambda d: d['steps'].append(copy.deepcopy(d['steps'][0])),
            lambda d: d['decisions'].append(copy.deepcopy(d['decisions'][0])),
            lambda d: d['decisions'][0].update(status='discarded_after_episode'),
            lambda d: d['steps'][0]['observation_before'].update(game_turn=4),
        ):
            data = episode()
            mutate(data)
            with self.assertRaises(ValueError):
                audit_episode(data)
        for turn, tick in ((3, 4.), (5, 2.)):
            data = episode()
            data['steps'][0]['done'] = False
            data['steps'].append({'turn': turn, 'elapsed_seconds': tick})
            with self.assertRaises(ValueError):
                audit_episode(data)

    def test_tick_before_request_with_missing_response_is_rejected(self):
        data = episode()
        decision = data['decisions'][0]
        for key in ('response_finished_seconds', 'applied_seconds'):
            del decision[key]
        decision['request_started_seconds'] = 4.
        with self.assertRaises(ValueError):
            audit_episode(data)

    def test_invalid_traffic(self):
        for cars in ('bad', [[1, 2]], [[1, float('nan'), 'right', 1, 1]],
                     [[1, 0, 'up', 1, 1]], [[1, 0, 'right', -1, 1]]):
            data = episode()
            data['decisions'][0]['observation']['state']['car_states'] = cars
            with self.assertRaises(ValueError):
                audit_episode(data)

    def test_cli_plain_gzip_and_failure(self):
        script = Path(__file__).with_name('freshness_audit.py')
        with tempfile.TemporaryDirectory() as directory:
            plain = Path(directory) / 'episode.json'
            zipped = Path(directory) / 'episode.json.gz'
            plain.write_text(json.dumps(episode()))
            with gzip.open(zipped, 'wt') as stream:
                json.dump(episode(), stream)
            result = subprocess.run([sys.executable, str(script), str(plain), str(zipped)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            reports = json.loads(result.stdout)
            self.assertEqual(len(reports), 2)
            self.assertEqual(reports[0]['decision_count'], 1)
            plain.write_text('{')
            result = subprocess.run([sys.executable, str(script), str(plain)],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, '')
            self.assertIn('audit failed', result.stderr)


if __name__ == '__main__':
    unittest.main()
