"""Offline failure/measurement tests. Run: python -m unittest test_decision_records."""
import copy
import unittest
from decision_records import decision_record
from run_model_freeway import parse_action


def response(content='S', reason='stop', **counts):
    return dict(message={'content':content}, done_reason=reason, **counts)


class DecisionRecordTests(unittest.TestCase):
    def test_valid_stay_is_not_fallback_and_missing_is_not_zero(self):
        raw = response(eval_count=0)
        before = copy.deepcopy(raw)
        record = decision_record(raw)
        self.assertTrue(record['valid_action'])
        self.assertEqual(record['parsed_action'], 'S')
        self.assertEqual(record['action_source'], 'model')
        self.assertIsNone(record['fallback_action'])
        self.assertIsNone(record['measurements']['input_tokens'])
        self.assertEqual(record['measurements']['output_tokens'], 0)
        self.assertNotIn('output_tokens', record['measurement_unavailable'])
        self.assertIsNone(record['measurements']['reasoning_tokens'])
        self.assertEqual(raw, before)

    def test_all_unusable_response_types(self):
        cases = [(None,'TimeoutError: timed out','timeout'),
                 (None,'ConnectionError: refused','request_error'),
                 ([],None,'malformed_response'), ({'message':None},None,'malformed_response'),
                 (response(None),None,'malformed_response'),
                 (response('U','length'),None,'token_limit_truncation'),
                 (response('U because traffic'),None,'invalid_action')]
        for raw, error, status in cases:
            with self.subTest(status=status):
                record = decision_record(raw,error)
                self.assertEqual(record['request_status'],status)
                self.assertIsNone(record['parsed_action'])
                self.assertEqual(record['fallback_action'],'S')
                self.assertEqual(record['action_source'],'invalid_fallback')
                self.assertIsNone(parse_action(raw,error))

    def test_late_response_stays_valid_but_is_not_applied(self):
        record = decision_record(response('U'), application_status='discarded_after_episode')
        self.assertTrue(record['valid_action'])
        self.assertEqual(record['application_status'], 'discarded_after_episode')
        self.assertEqual(record['response']['message']['content'],'U')
