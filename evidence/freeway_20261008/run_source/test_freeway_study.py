# These are local mechanics/logging tests, not measured model episodes.
import copy
import unittest
from types import SimpleNamespace

from freeway_study import (build_situations, dynamics_key, internal_state,
    recreate, simulate, quantile, episode_metrics, live_order)
from run_model_freeway import build_request, parse_action


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.situations = build_situations()

    def test_replay_and_noncosmetic_distinctness(self):
        # Replay from seed and prefix, including hidden car timers and RNG.
        keys = []
        for case in self.situations:
            env, actual = recreate(case['requested_seed'], case['preceding_actions'])
            self.assertEqual(actual, case['actual_seed'])
            self.assertEqual(internal_state(env), case['internal_state'])
            keys.append(dynamics_key(env))
        self.assertEqual(len(keys), 15)
        self.assertEqual(len(set(keys)), 15)
        self.assertEqual(build_situations(), self.situations)

    def test_action_copies_are_independent_including_collision_resets(self):
        for case in self.situations:
            env, _ = recreate(case['requested_seed'], case['preceding_actions'])
            before = internal_state(env)
            # Reverse action order to detect accidental shared mutations.
            for action in 'SDU':
                self.assertEqual(simulate(env, action), case['immediate'][action])
                self.assertEqual(internal_state(env), before)
            if case['category'] == 'waiting_useful':
                sequence = case['waiting_reference']['actions']
                result = simulate(env, sequence)
                self.assertFalse(result['collision'])
                self.assertGreater(result['position_change'], 0)
                self.assertTrue(case['immediate']['U']['collision'])

    def test_shared_sampling_seed_changes_only_sampling(self):
        observation = self.situations[0]['observation']
        args = SimpleNamespace(model='qwen3:4b-q4_K_M', prompt='progress',
            board='full', thinking='off', tick_seconds=1.0, model_seed=0)
        first = build_request(observation, args)
        args.model_seed = 2
        second = build_request(observation, args)
        first['options']['seed'] = 2
        self.assertEqual(first, second)
        for content, reason in [('U', 'length'), ('U because...', 'stop'), ('', 'stop')]:
            self.assertIsNone(parse_action({'message':{'content':content},'done_reason':reason}))

    def test_goal_and_timeout_with_empty_observation(self):
        # A small summary fixture checks terminal interpretation independently
        # of the full controller. It is never included in measured results.
        env, actual = recreate(0, '')
        env.pos = 1  # Explicit synthetic UNIT TEST position y=8.
        before = env.observe()
        after, done, score, collision = env.step('U')
        self.assertEqual(after, {})
        self.assertTrue(done)
        # Remove model decisions so this fixture tests just termination/progress.
        episode = dict(requested_seed=0, real_seed=actual,
            settings={'model_seed':0,'tick_seconds':1.0}, initial_observation=before,
            decisions=[], steps=[dict(turn=1, action='U', action_source='unit_test',
                observation_before=before, observation_after=after, done=done,
                collision=collision, scheduler_lag_seconds=.02)],
            summary=dict(success=True, turns=1, elapsed_seconds=1.02,
                         collisions=0, final_score=score))
        metrics = episode_metrics(episode)
        self.assertTrue(metrics['success'])
        self.assertEqual(metrics['maximum_position'], 9)
        # Empty terminal observation alone is not evidence of reaching the goal.
        episode['steps'][0]['action'] = 'S'
        episode['summary']['success'] = False
        metrics = episode_metrics(episode)
        self.assertFalse(metrics['success'])
        self.assertEqual(metrics['maximum_position'], 8)

    def test_latency_convention_and_matched_order(self):
        self.assertEqual(quantile([1,2,3,4,5], .9), 4.6)
        self.assertIsNone(quantile([], .5))
        order = live_order()
        self.assertEqual(len(order), 15)
        self.assertEqual(set(order), {(s,t) for s in range(5) for t in [1,2,4]})


if __name__ == '__main__':
    unittest.main()
