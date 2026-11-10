"""Offline observable-state/rendering checks; no inference or bank mutation.

Run python -m unittest test_freeway_observations -v. Exercises information
retention, boundary extents, deterministic IDs, empty lanes and leakage isolation.
"""
import copy
import unittest

from freeway_observations import FORMATS, canonical, footprint, render


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.observation = {'state': {'player_states': 2, 'car_states': [
            [1, -60, 'right', 3, 23], [2, 0, 'left', 12, 11],
            [3, None, None, None, None], [2, 12, 'right', 4, 11]],
            'game_turn': 99, 'random_state': 'SECRET'}, 'answer': 'SECRET'}

    def test_whitelist_and_stable_ids(self):
        original = copy.deepcopy(self.observation)
        view = canonical(self.observation)
        self.assertEqual(set(view), {'version', 'player', 'cars'})
        self.assertEqual([c['id'] for c in view['cars']], ['C00', 'C01', 'C03'])
        self.assertNotIn('SECRET', str(view))
        self.assertEqual(self.observation, original)

    def test_extents_are_not_wrapped(self):
        cars = canonical(self.observation)['cars']
        self.assertEqual(footprint(cars[0]), (-83, -60))
        self.assertEqual(footprint(cars[1]), (0, 11))
        self.assertEqual(footprint(cars[2]), (1, 12))

    def test_all_formats_preserve_objects_and_are_deterministic(self):
        view = canonical(self.observation)
        for name in FORMATS:
            with self.subTest(name=name):
                text = render(view, name)
                self.assertEqual(text, render(copy.deepcopy(view), name))
                for token in ('C00', 'C01', 'C03', '-60', '23', 'left', 'right'):
                    self.assertIn(token, text)
                self.assertNotIn('SECRET', text)
                self.assertNotIn('game_turn', text)
        relative = render(view, 'relative')
        self.assertIn('dlane=-1', relative)
        self.assertIn('dlane=0', relative)

    def test_empty_and_invalid(self):
        self.observation['state']['car_states'] = []
        for name in FORMATS:
            self.assertTrue(render(canonical(self.observation), name))
        with self.assertRaises(ValueError):
            render(canonical(self.observation), 'nearest')
        self.observation['state']['player_states'] = 9
        with self.assertRaises(ValueError):
            canonical(self.observation)


if __name__ == '__main__':
    unittest.main()
