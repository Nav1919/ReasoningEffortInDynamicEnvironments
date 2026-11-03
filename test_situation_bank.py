"""Check checkpoint replay and bounded labels against independent enumeration.

Run: .venv/bin/python -m unittest test_situation_bank -v. Inputs: local simulator
and temporary pilot banks. Outputs: assertions only; no model requests. Covers
situation_bank.py, including collision reset, goal, timeout and tied actions.
"""
import itertools
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from freeway_study import internal_state, recreate, simulate
from situation_bank import answer_key, balanced_bank, collect, digest, label, restore, verify


class SituationBankTests(unittest.TestCase):
    def test_search_matches_exhaustive_sequences(self):
        # Compare the search with every short action sequence, including ties.
        for prefix in ('', 'UU', 'UUU', 'UUUUSU'):
            env, _ = recreate(0, prefix)
            before = digest(internal_state(env))
            labels = answer_key(env, 3)
            for h in range(1, 4):
                possibilities = []
                for actions in itertools.product('UDS', repeat=h):
                    result = simulate(env, ''.join(actions))
                    goal = result['steps'][-1]['success']
                    if result['collision'] or (result['termination'] and not goal):
                        continue
                    score = (int(goal), -len(result['steps']) if goal else result['final_y'])
                    possibilities.append((actions[0], score))
                safe = {a for a, _ in possibilities}
                best = max((score for _, score in possibilities), default=None)
                optimal = {a for a, score in possibilities if score == best}
                entry = labels['by_horizon'][str(h)]
                self.assertEqual(set(entry['safe_first_actions']), safe)
                self.assertEqual(set(entry['best_first_actions']), optimal)
            self.assertEqual(digest(internal_state(env)), before)

    def test_goal_timeout_and_collision(self):
        # Edited states test edge cases only; they never enter the bank.
        env, _ = recreate(0, 'UUU')
        key = answer_key(env, 3)
        self.assertTrue(key['immediate']['U']['collision'])
        self.assertNotIn('U', key['by_horizon']['3']['safe_first_actions'])
        env, _ = recreate(0, '')
        env.pos = 1
        key = answer_key(env, 3)
        self.assertEqual(key['by_horizon']['3']['best_first_actions'], ['U'])
        self.assertEqual(key['by_horizon']['3']['outcomes']['U']['goal_ticks'], 1)
        env, _ = recreate(0, '')
        env.game_turn = 99
        self.assertEqual(answer_key(env, 2)['by_horizon']['2']['safe_first_actions'], [])
        env.pos = 1
        self.assertEqual(answer_key(env, 2)['by_horizon']['2']['best_first_actions'], ['U'])

    def test_collection_restore_rebuild_and_validation(self):
        with tempfile.TemporaryDirectory() as root:
            first, second = Path(root)/'first', Path(root)/'second'
            collect(first, count=10, selectors=2)
            collect(second, count=10, selectors=2)
            self.assertEqual((first/'states.json').read_bytes(), (second/'states.json').read_bytes())
            states = json.loads((first/'states.json').read_text())
            for record in states:
                restored = restore(record)
                replayed, _ = recreate(record['requested_seed'], record['preceding_actions'])
                self.assertEqual(digest(internal_state(restored)), record['state_sha256'])
                for actions in itertools.product('UDS', repeat=2):
                    self.assertEqual(simulate(restored, ''.join(actions)),
                                     simulate(replayed, ''.join(actions)))
            label(first, horizon=3)
            self.assertTrue(verify(first)['passed'])
            with self.assertRaises(ValueError):
                label(first, horizon=3)
            with self.assertRaises(ValueError):
                collect(first)
            states[0]['snapshot']['pos'] = 8
            (first/'states.json').write_text(json.dumps(states))
            with self.assertRaises(ValueError):
                verify(first)

    def test_argument_limits(self):
        env, _ = recreate(0, '')
        for h in (0, 11):
            with self.assertRaises(ValueError):
                answer_key(env, h)

    def test_balanced_collection_is_reachable_and_reproducible(self):
        with tempfile.TemporaryDirectory() as root:
            first, second = Path(root)/'first', Path(root)/'second'
            for path in (first, second):
                report = balanced_bank(path, count=16, selectors=1, ticks=10, horizon=3)
                self.assertTrue(report['passed'])
                manifest = json.loads((path/'manifest.json').read_text())
                labels = json.loads((path/'labels.json').read_text())
                self.assertEqual(manifest['count'], 16)
                self.assertEqual(sum(manifest['selected_category_counts'].values()), 16)
                self.assertNotIn('other', manifest['selected_category_counts'])
                self.assertEqual(manifest['selected_actual_seeds'], [1000])
                self.assertEqual(dict(Counter(k['category'] for k in labels)),
                                 manifest['selected_category_counts'])
                self.assertGreater(len(manifest['lane_counts']), 1)
            self.assertEqual((first/'states.json').read_bytes(), (second/'states.json').read_bytes())
            self.assertEqual((first/'labels.json').read_bytes(), (second/'labels.json').read_bytes())
            with self.assertRaises(ValueError):
                balanced_bank(Path(root)/'invalid', selectors=6)

    def test_shared_cache_preserves_answers(self):
        cache = {}
        for prefix in ('', 'U', 'UU', 'UUU'):
            env, _ = recreate(0, prefix)
            standalone = answer_key(env, 3)
            shared = answer_key(env, 3, cache)
            standalone.pop('search_states')
            shared.pop('search_states')
            self.assertEqual(standalone, shared)


if __name__ == '__main__':
    unittest.main()
