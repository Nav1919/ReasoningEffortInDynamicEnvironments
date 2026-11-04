"""Check checkpoint replay and bounded labels against independent enumeration.

Run: .venv/bin/python -m unittest test_freeway_scenarios -v. Inputs: local simulator
and temporary pilot banks. Outputs: assertions only; no model requests. Covers
freeway_scenarios.py, including collision reset, goal, timeout and tied actions.
"""
import itertools
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from freeway_study import internal_state, recreate, simulate
from freeway_scenarios import answer_key, digest, generate, load, main, run


class FreewayScenarioTests(unittest.TestCase):
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

    def test_argument_limits(self):
        env, _ = recreate(0, '')
        for h in (0, 11):
            with self.assertRaises(ValueError):
                answer_key(env, h)

    def test_one_file_generation_replay_and_categories(self):
        with tempfile.TemporaryDirectory() as root:
            first, second = Path(root)/'first.json', Path(root)/'second.json'
            for path in (first, second):
                bank = generate(path, count=16, selectors=1, ticks=10, horizon=3)
                self.assertTrue(bank['metadata']['verification']['passed'])
                self.assertEqual(len(bank['scenarios']), 16)
                self.assertEqual(dict(Counter(s['category'] for s in bank['scenarios'])),
                                 bank['metadata']['category_counts'])
                self.assertEqual(len({s['dynamics_sha256'] for s in bank['scenarios']}), 16)
                self.assertEqual(load(path), json.loads(path.read_text()))
                self.assertTrue(run(load(path), scenario_id=0)['passed'])
                category = bank['scenarios'][0]['category']
                report = run(load(path), category=category)
                self.assertEqual(report['scenarios_verified'],
                                 bank['metadata']['category_counts'][category])
                with self.assertRaises(ValueError):
                    run(bank, scenario_id=999)
                with self.assertRaises(ValueError):
                    generate(path)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(main(['summary', '--file', str(first)]), 0)
            self.assertEqual(main(['run', '--id', '0', '--file', str(first)]), 0)
            self.assertEqual(main(['run', '--all', '--file', str(first)]), 0)
            self.assertEqual(main(['run', '--category', category, '--file', str(first)]), 0)
            bank = load(first)
            bank['scenarios'][0]['category'] = 'invalid'
            first.write_text(json.dumps(bank))
            with self.assertRaises(ValueError):
                load(first)
            with self.assertRaises(ValueError):
                generate(Path(root)/'invalid.json', selectors=6)

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
