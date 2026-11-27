"""Offline replay/debugger regression checks; never call Ollama.

Run: python -m unittest discover -s tests -p 'test_decision_replay.py' -v
Inputs: real seeded Freeway transitions with explicitly synthetic model text.
Outputs: unittest assertions and temporary files only. Tests cover state replay,
corrupt evidence, exact saved text, failed runs, seeking and SDL dummy rendering.
Implementation: decision_model_experiments/replay.py and replay_gui.py.
"""

import copy
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from decision_model_experiments.experiment_runner import _make_freeway
from decision_model_experiments.replay import ReplayTrace, load_trace, main, plain
from decision_model_experiments.replay_gui import ReplayCursor, ReplayWindow


def episode_fixture(mode="both", actions=("U", "U", "U", "U")):
    """Real simulator states, synthetic trace text; no inference or study result."""
    env, seed, _ = _make_freeway(0)
    observation, done = env.reset()
    initial = plain(observation)
    steps = []
    collisions = 0
    for index, action in enumerate(actions):
        before = plain(observation)
        observation, done, score, collision = env.step(action)
        collisions += int(collision)
        steps.append({
            "turn": int(env.game_turn), "action": action, "source": "actor",
            "score": float(score), "collision": bool(collision), "done": bool(done),
            "revealed_token_count": min(2 * (index + 1), 6) if mode != "observation" else 0,
            "observer_cycle_id": 7 if mode != "observation" else None,
            "context": "saved context\n  exact spaces", "context_mode": mode,
            "observation_before": before, "observation_after": plain(observation),
            "actor_result": {"prompt": "ACTUAL SAVED PROMPT\n  keep indentation",
                             "content": action, "thinking": "", "error": None},
        })
    return {
        "environment": "Freeway-v0", "requested_seed": 0, "real_seed": int(seed),
        "initial_observation": initial,
        "settings": {"context_mode": mode, "tokenization_method": "whitespace"},
        "steps": steps,
        "observer_cycles": [] if mode == "observation" else [{
            "id": 7, "observation": initial, "reasoning": "one two\nthree four five six",
            "tokenization_method": "whitespace", "token_count": 6,
            "generation": {"prompt": "SAVED OBSERVER PROMPT", "error": None},
        }],
        "summary": {"turns": int(env.game_turn), "collisions": collisions,
                    "final_score": float(env.reward), "episode_ended": bool(done),
                    "success": bool(done and steps[-1]["action"] == "U" and
                                    steps[-1]["observation_before"]["state"]["player_states"] == 8),
                    "error": None},
    }


class ReplayEvidenceTests(unittest.TestCase):
    def test_all_modes_replay_without_model_calls_and_detach_states(self):
        for mode in ("observation", "reasoning", "both"):
            with self.subTest(mode=mode), patch(
                "decision_model_experiments.models.post_json", side_effect=AssertionError("No inference")
            ):
                episode = episode_fixture(mode)
                before = copy.deepcopy(episode)
                replay = ReplayTrace.verify(episode)
                self.assertEqual(replay.report()["verified_steps"], 4)
                self.assertEqual(len(replay.states), 5)
                self.assertEqual(replay.state(0).pos, 9)
                self.assertEqual(replay.state(0, after=True).game_turn, 1)
                self.assertEqual(replay.state(3, after=True).game_turn, 4)
                self.assertIsNot(replay.states[0].cars, replay.states[1].cars)
                self.assertEqual(episode, before)

    def test_collisions_and_terminal_replay(self):
        episode = episode_fixture(actions=("U",) * 100)
        trace = ReplayTrace.verify(episode)
        self.assertGreater(trace.report()["collisions"], 0)
        self.assertTrue(trace.states[-1].terminal)
        self.assertFalse(episode["summary"]["success"])

    def test_corrupt_seed_observations_transitions_and_summary_are_rejected(self):
        def bad_action(d):
            d["steps"][0]["action"] = "X"
        mutations = [
            lambda d: d.update(real_seed=12345),
            lambda d: d["initial_observation"].update(state_string="bad"),
            lambda d: d["steps"][0]["observation_before"].update(state_string="bad"),
            lambda d: d["steps"][0].update(score=-999),
            lambda d: d["steps"][0].update(collision=not d["steps"][0]["collision"]),
            lambda d: d["steps"][0].update(done=True),
            lambda d: d["steps"][0].update(observer_cycle_id=123),
            lambda d: d["summary"].update(success=True),
            bad_action,
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                episode = episode_fixture()
                mutate(episode)
                with self.assertRaises(ValueError):
                    ReplayTrace.verify(episode)

    def test_actions_after_termination_are_rejected(self):
        episode = episode_fixture(actions=("U",) * 100)
        episode["steps"].append(copy.deepcopy(episode["steps"][-1]))
        with self.assertRaisesRegex(ValueError, "after termination"):
            ReplayTrace.verify(episode)

    def test_saved_prompts_and_prefix_not_recreated_from_current_agent(self):
        trace = ReplayTrace.verify(episode_fixture())
        panels = trace.panels(0)
        self.assertIn("ACTUAL SAVED PROMPT\n  keep indentation", panels["Actor prompt"])
        self.assertIn("saved context\n  exact spaces", panels["Actor prompt"])
        self.assertIn("SAVED OBSERVER PROMPT", panels["Observer prompt"])
        revealed, rest = panels["Reasoning"].split("NOT YET REVEALED TO ACTOR")
        self.assertIn("one two", revealed)
        self.assertNotIn("three", revealed)
        self.assertIn("three four five six", rest)
        self.assertIn("one two\nthree four five six", rest)
        self.assertEqual(trace.cycle(0)["id"], 7)  # ID is not a list index.

    def test_unknown_tokenization_shows_saved_context_without_guessing(self):
        episode = episode_fixture()
        episode["observer_cycles"][0]["tokenization_method"] = "future-method"
        panels = ReplayTrace.verify(episode).panels(0)
        self.assertIn("unknown tokenizer", panels["Reasoning"])
        self.assertIn("saved context", panels["Actor prompt"])

    def test_fallback_and_generation_errors_are_preserved(self):
        episode = episode_fixture()
        episode["steps"][0]["source"] = "fallback"
        episode["steps"][0]["actor_result"].update(error="Connection refused", content="invalid prose")
        episode["summary"]["error"] = "Interrupted run"
        trace = ReplayTrace.verify(episode)
        self.assertIn("Connection refused", trace.panels(0)["Outputs"])
        self.assertIn("invalid prose", trace.panels(0)["Outputs"])
        self.assertEqual(trace.report()["episode_error"], "Interrupted run")

    def test_failed_setup_is_readable_and_not_marked_verified(self):
        episode = episode_fixture(actions=())
        episode.update(initial_observation=None, real_seed=None)
        episode["summary"].update(error="ConnectionError: offline", final_score=None)
        trace = ReplayTrace.verify(episode)
        self.assertEqual(trace.states, [])
        self.assertEqual(trace.report()["verification"], "no game state recorded")
        self.assertIn("ConnectionError", trace.panels(0)["Episode"])

    def test_empty_observer_failure_without_steps_remains_readable(self):
        episode = episode_fixture(actions=())
        episode["observer_cycles"][0].update(reasoning="", error="empty trace")
        episode["summary"]["error"] = "empty observer trace produced no reveal steps"
        trace = ReplayTrace.verify(episode)
        self.assertEqual(len(trace.states), 1)
        self.assertIsNone(trace.step(0))
        self.assertIn("SAVED OBSERVER PROMPT", trace.panels(0)["Observer prompt"])
        self.assertIn("empty observer", trace.panels(0)["Episode"])

    def test_observation_mode_and_missing_prompts_are_explicit(self):
        episode = episode_fixture("observation")
        episode["steps"][0]["actor_result"] = None
        panels = ReplayTrace.verify(episode).panels(0)
        self.assertIn("No observer call", panels["Reasoning"])
        self.assertIn("Not recorded", panels["Actor prompt"])

    def test_json_gzip_and_verify_only_do_not_write_source_or_open_gui(self):
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".json", ".json.gz"):
                path = Path(directory) / ("episode" + suffix)
                opener = gzip.open if suffix.endswith("gz") else open
                with opener(path, "wt", encoding="utf-8") as output:
                    json.dump(episode_fixture(), output)
                original = path.read_bytes()
                self.assertEqual(load_trace(path).report()["verified_steps"], 4)
                with patch.object(ReplayWindow, "__init__", side_effect=AssertionError("No GUI")):
                    result = main([str(path), "--verify-only"])
                self.assertEqual(result["verified_steps"], 4)
                self.assertEqual(path.read_bytes(), original)

    def test_invalid_file_cli_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{}")
            with self.assertRaises(SystemExit) as error:
                main([str(path), "--verify-only"])
            self.assertEqual(error.exception.code, 1)


class ReplayNavigationTests(unittest.TestCase):
    def test_seek_clamps_and_playback_stops_at_end(self):
        cursor = ReplayCursor(4)
        cursor.seek(-20)
        self.assertEqual(cursor.index, 0)
        cursor.seek(3)
        cursor.playing = True
        cursor.advance()
        self.assertEqual(cursor.index, 3)
        self.assertFalse(cursor.playing)
        cursor.seek(999)
        self.assertEqual(cursor.index, 3)
        empty = ReplayCursor(0)
        empty.advance()
        self.assertEqual(empty.index, 0)
        self.assertFalse(empty.playing)


class ReplayPygameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = patch.dict(os.environ, {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
        cls.environment.start()
        import pygame
        pygame.quit()
        cls.pygame = pygame

    @classmethod
    def tearDownClass(cls):
        cls.pygame.quit()
        cls.environment.stop()

    def setUp(self):
        self.window = ReplayWindow(ReplayTrace.verify(episode_fixture()), "synthetic_test.json")
        self.addCleanup(self.pygame.display.quit)

    def key(self, key):
        self.window.handle_event(self.pygame.event.Event(self.pygame.KEYDOWN, key=key))

    def test_keyboard_phase_tabs_scroll_seek_and_resize(self):
        pg = self.pygame
        self.key(pg.K_RIGHT)
        self.key(pg.K_b)
        self.assertEqual(self.window.cursor.index, 1)
        self.assertTrue(self.window.cursor.after)
        self.key(pg.K_TAB)
        self.assertEqual(self.window.tab, "Reasoning")
        self.window._select_tab("Episode")
        self.key(pg.K_PAGEDOWN)
        self.window.draw()
        self.assertGreater(self.window.scroll, 0)
        self.window.handle_event(pg.event.Event(pg.VIDEORESIZE, w=900, h=500))
        self.window.draw()
        self.assertEqual(self.window.screen.get_size(), (1140, 760))
        self.key(pg.K_END)
        self.assertEqual(self.window.cursor.index, 3)
        self.key(pg.K_HOME)
        self.assertEqual(self.window.cursor.index, 0)
        self.key(pg.K_SPACE)
        self.assertTrue(self.window.cursor.playing)
        self.key(pg.K_ESCAPE)
        self.assertFalse(self.window.running)

    def test_click_seek_tab_and_next_issue(self):
        pg = self.pygame
        self.window.trace.episode["steps"][2]["source"] = "fallback"
        self.key(pg.K_n)
        self.assertEqual(self.window.cursor.index, 2)
        self.window.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, button=1,
                                               pos=self.window.timeline.topleft))
        self.assertEqual(self.window.cursor.index, 0)
        # Drawn button callbacks also work with actual mouse coordinates.
        self.window.draw()
        rect, _ = self.window.buttons[1]
        self.window.handle_event(pg.event.Event(pg.MOUSEBUTTONDOWN, button=1, pos=rect.center))
        self.assertEqual(self.window.tab, "Reasoning")

    def test_pause_at_last_step_does_not_restart_and_play_can_restart(self):
        self.window.cursor.seek(3)
        self.window.cursor.playing = True
        self.window._play()
        self.assertFalse(self.window.cursor.playing)
        self.assertEqual(self.window.cursor.index, 3)
        self.window._play()
        self.assertTrue(self.window.cursor.playing)
        self.assertEqual(self.window.cursor.index, 0)

    def test_event_loop_closes_display_on_quit(self):
        self.pygame.event.post(self.pygame.event.Event(self.pygame.QUIT))
        self.window.run()
        self.assertFalse(self.pygame.display.get_init())

    def test_all_tabs_draw_and_long_words_wrap(self):
        for name in self.window.TABS:
            self.window._select_tab(name)
            self.window.draw()
        lines = self.window._wrapped("x" * 1000 + "\n  indent", 200)
        self.assertGreater(len(lines), 20)
        self.assertEqual(lines[-1], "  indent")

    def test_failed_run_renders_without_board(self):
        episode = episode_fixture(actions=())
        episode.update(initial_observation=None)
        episode["summary"].update(error="setup failed")
        window = ReplayWindow(ReplayTrace.verify(episode), "failed.json")
        window.draw()
        self.assertEqual(window.tab, "Episode")
        window._play()
        self.assertFalse(window.cursor.playing)


if __name__ == "__main__":
    unittest.main()
