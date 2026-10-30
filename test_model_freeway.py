# Small regression checks for the boundary between model text and game actions.
# They do not call Ollama and cannot be mistaken for episode performance.
import copy
import unittest
from run_model_freeway import build_prompt, parse_action


class ModelBoundaryTests(unittest.TestCase):
    def test_only_complete_single_actions_are_accepted(self):
        # In particular, don't turn explanatory prose or truncated output into U.
        for text, reason, expected in [
            ('U', 'stop', 'U'), (' d\n', 'stop', 'D'), ('S', 'stop', 'S'),
            ('Choose U', 'stop', None), ('U S', 'stop', None),
            ('U', 'length', None), ('', 'stop', None),
        ]:
            with self.subTest(text=text, reason=reason):
                response = {'message': {'content': text, 'thinking': 'U'},
                            'done_reason': reason}
                self.assertEqual(parse_action(response), expected)
        self.assertIsNone(parse_action(None, 'HTTP failed'))

    def test_board_removal_is_independent_and_does_not_mutate_snapshot(self):
        observation = {'state_string': 'BOARD_MARKER', 'game_turn': 0,
                       'state': {'player_states': 0, 'car_states': []}}
        saved = copy.deepcopy(observation)
        for strategy in ['original', 'progress']:
            full = build_prompt(observation, 1.0, strategy, 'full')
            structured = build_prompt(observation, 1.0, strategy, 'structured')
            self.assertIn('BOARD_MARKER', full)
            self.assertNotIn('BOARD_MARKER', structured)
            self.assertIn('"player_states": 0', structured)
            self.assertEqual(full.split('Observation:')[0],
                             structured.split('Observation:')[0])
        self.assertEqual(observation, saved)


if __name__ == '__main__':
    unittest.main()
