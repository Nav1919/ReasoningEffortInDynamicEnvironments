# Offline checks for the runner-owned reveal schedule, actor context,
# episode loop, and JSON log. They do not call Ollama and cannot be
# mistaken for episode performance.
import argparse
import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from decision_model_experiments.actor_agent import ActorAgent
from decision_model_experiments.experiment_runner import (
    CONTEXT_MODES,
    OBSERVATION_FRESHNESS,
    OBSERVATION_LABEL,
    REVEALED_REASONING_LABEL,
    TOKENIZATION_METHOD,
    ExperimentRunner,
    build_actor_context,
    count_reasoning_tokens,
    join_reasoning_tokens,
    parse_args,
    reveal_prefix_lengths,
    revealed_reasoning_prefixes,
    tokenize_reasoning,
    unused_reasoning_from_trace,
)
from decision_model_experiments.models import GenerationResult, ModelClient, ModelConfig


TEN_TOKEN_TRACE = "t1 t2 t3 t4 t5 t6 t7 t8 t9 t10"
REVEALED_PREFIX = "UNIQUE_REASONING_PREFIX cars approaching"
FROZEN_OBSERVATION = {
    "state_string": "FROZEN_BOARD",
    "game_turn": 0,
    "state": {"player_states": 0, "car_states": []},
}
LIVE_OBSERVATION = {
    "state_string": "LIVE_BOARD",
    "game_turn": 2,
    "state": {"player_states": 3, "car_states": [[1, 12, "right", 6, 4]]},
}


class TokenizationMethodTests(unittest.TestCase):
    def test_method_is_the_named_whitespace_approximation(self):
        # Model tokenization is unavailable offline. The method name is what
        # later episode logs must record; do not switch it silently.
        self.assertEqual(TOKENIZATION_METHOD, "whitespace")
        self.assertEqual(tokenize_reasoning(TEN_TOKEN_TRACE), TEN_TOKEN_TRACE.split())
        self.assertEqual(count_reasoning_tokens(TEN_TOKEN_TRACE), 10)
        self.assertEqual(count_reasoning_tokens(""), 0)
        self.assertEqual(count_reasoning_tokens("   "), 0)
        self.assertEqual(
            join_reasoning_tokens(["t1", "t2", "t3"]),
            "t1 t2 t3",
        )

    def test_unknown_method_is_rejected(self):
        with self.assertRaises(ValueError) as raised:
            tokenize_reasoning(TEN_TOKEN_TRACE, method="characters")
        self.assertIn("whitespace", str(raised.exception))


class RevealScheduleTests(unittest.TestCase):
    def test_ten_tokens_pressure_three_makes_four_prefixes(self):
        lengths = reveal_prefix_lengths(10, 3)
        prefixes = revealed_reasoning_prefixes(TEN_TOKEN_TRACE, 3)
        self.assertEqual(lengths, [3, 6, 9, 10])
        self.assertEqual(len(prefixes), 4)
        self.assertEqual(
            [count_reasoning_tokens(prefix) for prefix in prefixes],
            [3, 6, 9, 10],
        )
        self.assertEqual(prefixes[0], "t1 t2 t3")
        self.assertEqual(prefixes[1], "t1 t2 t3 t4 t5 t6")
        self.assertEqual(prefixes[2], "t1 t2 t3 t4 t5 t6 t7 t8 t9")
        self.assertEqual(prefixes[3], TEN_TOKEN_TRACE)

    def test_empty_trace_does_not_invent_steps(self):
        self.assertEqual(reveal_prefix_lengths(0, 3), [])
        self.assertEqual(revealed_reasoning_prefixes("", 3), [])
        self.assertEqual(revealed_reasoning_prefixes("   ", 3), [])

    def test_short_trace_uses_actual_token_count(self):
        # Observer budget x=10 would overstate the schedule. Five actual
        # tokens at pressure 3 is two prefixes, not four.
        short_trace = "a b c d e"
        self.assertEqual(count_reasoning_tokens(short_trace), 5)
        self.assertEqual(reveal_prefix_lengths(5, 3), [3, 5])
        self.assertEqual(
            revealed_reasoning_prefixes(short_trace, 3),
            ["a b c", "a b c d e"],
        )

    def test_pressure_larger_than_trace_is_one_full_prefix(self):
        self.assertEqual(reveal_prefix_lengths(2, 3), [2])
        self.assertEqual(revealed_reasoning_prefixes("a b", 3), ["a b"])

    def test_exact_multiple_has_no_partial_final_chunk(self):
        self.assertEqual(reveal_prefix_lengths(9, 3), [3, 6, 9])

    def test_invalid_time_pressure_is_rejected(self):
        with self.assertRaises(ValueError):
            reveal_prefix_lengths(10, 0)
        with self.assertRaises(ValueError):
            revealed_reasoning_prefixes(TEN_TOKEN_TRACE, -1)

    def test_helpers_do_not_take_context_mode_or_x(self):
        # x is the observer generation budget. The schedule uses actual
        # token count. context_mode belongs to build_actor_context.
        for function in (
            tokenize_reasoning,
            count_reasoning_tokens,
            reveal_prefix_lengths,
            revealed_reasoning_prefixes,
        ):
            parameters = inspect.signature(function).parameters
            self.assertNotIn("context_mode", parameters)
            self.assertNotIn("x", parameters)
            self.assertNotIn("observer_tokens", parameters)


class ActorContextBuilderTests(unittest.TestCase):
    def test_freshness_policy_is_live(self):
        self.assertEqual(OBSERVATION_FRESHNESS, "live")
        self.assertEqual(CONTEXT_MODES, ("reasoning", "observation", "both"))

    def test_observation_mode_is_live_state_only(self):
        # Even a non-empty revealed prefix must stay out of this mode.
        context = build_actor_context(
            "observation", REVEALED_PREFIX, LIVE_OBSERVATION,
        )
        self.assertIn(OBSERVATION_LABEL, context)
        self.assertIn("LIVE_BOARD", context)
        self.assertIn('"player_states": 3', context)
        self.assertNotIn(REVEALED_REASONING_LABEL, context)
        self.assertNotIn(REVEALED_PREFIX, context)
        self.assertNotIn("FROZEN_BOARD", context)

    def test_reasoning_mode_is_revealed_prefix_only(self):
        # A live (or frozen) observation passed in must not appear.
        context = build_actor_context(
            "reasoning", REVEALED_PREFIX, LIVE_OBSERVATION,
        )
        self.assertIn(REVEALED_REASONING_LABEL, context)
        self.assertIn(REVEALED_PREFIX, context)
        self.assertNotIn(OBSERVATION_LABEL, context)
        self.assertNotIn("LIVE_BOARD", context)
        self.assertNotIn("FROZEN_BOARD", context)
        self.assertNotIn('"player_states": 3', context)

    def test_both_mode_uses_revealed_prefix_and_live_observation(self):
        # The frozen observer snapshot is a different dict the builder never
        # receives. both must show the live state after inner steps.
        context = build_actor_context("both", REVEALED_PREFIX, LIVE_OBSERVATION)
        self.assertIn(REVEALED_REASONING_LABEL, context)
        self.assertIn(REVEALED_PREFIX, context)
        self.assertIn(OBSERVATION_LABEL, context)
        self.assertIn("LIVE_BOARD", context)
        self.assertIn('"player_states": 3', context)
        self.assertNotIn("FROZEN_BOARD", context)
        self.assertLess(
            context.index(REVEALED_PREFIX),
            context.index("LIVE_BOARD"),
        )

    def test_both_does_not_substitute_the_frozen_observer_snapshot(self):
        frozen_context = build_actor_context(
            "both", REVEALED_PREFIX, FROZEN_OBSERVATION,
        )
        live_context = build_actor_context(
            "both", REVEALED_PREFIX, LIVE_OBSERVATION,
        )
        self.assertIn("FROZEN_BOARD", frozen_context)
        self.assertNotIn("LIVE_BOARD", frozen_context)
        self.assertIn("LIVE_BOARD", live_context)
        self.assertNotIn("FROZEN_BOARD", live_context)

    def test_structured_board_drops_the_text_drawing_only(self):
        saved = copy.deepcopy(LIVE_OBSERVATION)
        full = build_actor_context(
            "observation", "", LIVE_OBSERVATION, board="full",
        )
        structured = build_actor_context(
            "observation", "", LIVE_OBSERVATION, board="structured",
        )
        self.assertIn("LIVE_BOARD", full)
        self.assertNotIn("LIVE_BOARD", structured)
        self.assertIn('"player_states": 3', structured)
        self.assertEqual(LIVE_OBSERVATION, saved)

    def test_unknown_context_mode_is_rejected(self):
        with self.assertRaises(ValueError) as raised:
            build_actor_context("observer_snapshot", REVEALED_PREFIX, LIVE_OBSERVATION)
        self.assertIn("context_mode", str(raised.exception))


def _args(log_path, **overrides):
    values = dict(
        context_mode="observation",
        time_pressure=3,
        observer_tokens=10,
        seed=0,
        model="qwen3:4b-q4_K_M",
        model_seed=0,
        thinking="on",
        board="full",
        log_path=log_path,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _generation(content, latency=0.05, error=None):
    return GenerationResult(
        prompt="stub",
        max_tokens=10,
        think=True,
        payload={"model": "stub"},
        response=None if error else {
            "message": {"content": content},
            "done_reason": "stop",
        },
        error=error,
        content=content,
        thinking="",
        done_reason=None if error else "stop",
        output_tokens=len(str(content).split()),
        input_tokens=4,
        latency_seconds=latency,
    )


class RaisingObserver:
    def think(self, observation):
        raise AssertionError("observer.think must not be called in observation mode")


class StubObserver:
    def __init__(self, traces):
        self.traces = list(traces)
        self.calls = []
        self.last_result = None

    def think(self, observation):
        self.calls.append(copy.deepcopy(observation))
        text = self.traces.pop(0) if self.traces else ""
        self.last_result = _generation(text)
        return text


class RecordingActor:
    def __init__(self, action="S", source="actor"):
        self.action = action
        self.calls = []
        self.last_result = None
        self.last_action_source = source

    def act(self, context):
        self.calls.append(context)
        return self.action


class FakeEnv:
    def __init__(self, observations, done_after, collisions=(), events=None):
        self._observations = [copy.deepcopy(item) for item in observations]
        self.done_after = done_after
        self.collisions_on = set(collisions)
        self.events = events if events is not None else []
        self.game_turn = 0
        self.reward = 100.0
        self.actions = []
        self.summary_calls = 0

    def reset(self):
        self.events.append("reset")
        self.game_turn = 0
        self.reward = 100.0
        return copy.deepcopy(self._observations[0]), False

    def step(self, action):
        self.actions.append(action)
        self.game_turn += 1
        self.reward -= 1
        done = self.game_turn >= self.done_after
        collided = self.game_turn in self.collisions_on
        if done:
            observation = {}
        else:
            index = min(self.game_turn, len(self._observations) - 1)
            observation = copy.deepcopy(self._observations[index])
        return observation, done, float(self.reward), collided

    def summary(self):
        self.summary_calls += 1


EXPECTED_SETTINGS_KEYS = {
    "model", "seed", "model_seed", "observer_tokens", "time_pressure",
    "context_mode", "observation_freshness", "tokenization_method",
    "observer_tokens_unused", "time_pressure_unused", "thinking",
    "thinking_unused", "board", "fallback_action", "actor_thinking",
    "log_path",
}
EXPECTED_STEP_KEYS = {
    "turn", "revealed_token_count", "context_mode", "context", "action",
    "source", "score", "collision", "done",
}
EXPECTED_SUMMARY_KEYS = {
    "turns", "collisions", "final_score", "success",
    "unused_reasoning_tokens", "observer_call_count",
}


class ParseArgsTests(unittest.TestCase):
    def test_refuses_an_existing_log_path(self):
        with tempfile.NamedTemporaryFile() as existing:
            with self.assertRaises(SystemExit):
                parse_args([
                    "--context-mode", "observation",
                    "--log-path", existing.name,
                ])

    def test_requires_context_mode(self):
        with self.assertRaises(SystemExit):
            parse_args([])

    def test_observer_tokens_short_flag_and_thinking_default(self):
        args = parse_args([
            "--context-mode", "both", "-x", "10", "--time-pressure", "3",
        ])
        self.assertEqual(args.observer_tokens, 10)
        self.assertEqual(args.time_pressure, 3)
        self.assertEqual(args.thinking, "on")
        self.assertEqual(args.model, "qwen3:4b-q4_K_M")


class ExperimentRunnerLoopTests(unittest.TestCase):
    def _run(self, observer, actor, env, **overrides):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        log_path = Path(directory) / "episode.json"
        events = env.events
        args = _args(str(log_path), **overrides)

        def fake_post(endpoint, payload):
            events.append(endpoint)
            if endpoint == "show":
                return {"model": "stub-qwen", "details": {}}
            return {"message": {"content": "S"}, "done_reason": "stop"}

        runner = ExperimentRunner(observer, actor, args)
        with patch(
            "decision_model_experiments.experiment_runner.post_json",
            fake_post,
        ), patch(
            "decision_model_experiments.experiment_runner._make_freeway",
            return_value=(env, 1000, None),
        ):
            episode = runner.run()
        saved = json.loads(log_path.read_text())
        return episode, saved, events, log_path

    def test_constructor_does_not_take_an_injected_environment(self):
        parameters = list(inspect.signature(ExperimentRunner.__init__).parameters)
        self.assertEqual(parameters, ["self", "observer", "actor", "args"])

    def test_warmup_and_metadata_happen_before_reset(self):
        events = []
        env = FakeEnv([LIVE_OBSERVATION], done_after=1, events=events)
        self._run(RaisingObserver(), RecordingActor(), env, context_mode="observation")
        self.assertEqual(events[:3], ["show", "chat", "reset"])

    def test_observation_never_calls_think_and_acts_once_per_state(self):
        observer = RaisingObserver()
        actor = RecordingActor("S")
        env = FakeEnv(
            [FROZEN_OBSERVATION, LIVE_OBSERVATION],
            done_after=3,
        )
        episode, saved, _, _ = self._run(
            observer, actor, env, context_mode="observation",
            observer_tokens=10, time_pressure=3,
        )
        self.assertEqual(env.actions, ["S", "S", "S"])
        self.assertEqual(len(actor.calls), 3)
        self.assertEqual(len(episode["steps"]), 3)
        self.assertEqual(episode["observer_cycles"], [])
        self.assertEqual(saved["summary"]["observer_call_count"], 0)
        self.assertTrue(saved["settings"]["observer_tokens_unused"])
        self.assertTrue(saved["settings"]["time_pressure_unused"])
        for step, context in zip(saved["steps"], actor.calls):
            self.assertEqual(step["revealed_token_count"], 0)
            self.assertEqual(step["context_mode"], "observation")
            self.assertEqual(step["source"], "actor")
            self.assertIn(OBSERVATION_LABEL, context)
            self.assertNotIn(REVEALED_REASONING_LABEL, context)
            self.assertNotIn(REVEALED_PREFIX, context)
        self.assertIn("FROZEN_BOARD", actor.calls[0])
        self.assertIn("LIVE_BOARD", actor.calls[1])
        self.assertEqual(env.summary_calls, 1)

    def test_inner_loop_uses_actual_token_count_not_x(self):
        # x=10 would be four prefixes at pressure 3. Five actual tokens is two
        # prefixes; a second five-token trace then fills the remaining two steps.
        observer = StubObserver(["a b c d e", "f g h i j"])
        actor = RecordingActor("U")
        env = FakeEnv([FROZEN_OBSERVATION, LIVE_OBSERVATION], done_after=4)
        episode, saved, _, _ = self._run(
            observer, actor, env,
            context_mode="reasoning",
            observer_tokens=10,
            time_pressure=3,
        )
        self.assertEqual(len(observer.calls), 2)
        self.assertEqual(len(actor.calls), 4)
        self.assertEqual(
            [step["revealed_token_count"] for step in saved["steps"]],
            [3, 5, 3, 5],
        )
        self.assertEqual(saved["summary"]["observer_call_count"], 2)
        self.assertEqual(saved["summary"]["unused_reasoning_tokens"], 0)
        self.assertFalse(saved["settings"]["observer_tokens_unused"])
        self.assertFalse(saved["settings"]["time_pressure_unused"])

    def test_episode_end_mid_trace_does_not_call_act_again(self):
        observer = StubObserver([TEN_TOKEN_TRACE])
        actor = RecordingActor("S")
        env = FakeEnv([FROZEN_OBSERVATION, LIVE_OBSERVATION], done_after=2)
        episode, saved, _, _ = self._run(
            observer, actor, env,
            context_mode="reasoning",
            observer_tokens=10,
            time_pressure=3,
        )
        self.assertEqual(len(observer.calls), 1)
        self.assertEqual(len(actor.calls), 2)
        self.assertEqual(
            [step["revealed_token_count"] for step in saved["steps"]],
            [3, 6],
        )
        self.assertEqual(saved["summary"]["unused_reasoning_tokens"], 4)
        leftover, leftover_count = unused_reasoning_from_trace(TEN_TOKEN_TRACE, 6)
        self.assertEqual(leftover_count, 4)
        self.assertEqual(saved["summary"]["unused_reasoning"], leftover)
        self.assertTrue(saved["steps"][-1]["done"])

    def test_reasoning_context_excludes_live_observation(self):
        observer = StubObserver([TEN_TOKEN_TRACE])
        actor = RecordingActor("S")
        env = FakeEnv([LIVE_OBSERVATION], done_after=1)
        _, _, _, _ = self._run(
            observer, actor, env, context_mode="reasoning",
        )
        self.assertIn(REVEALED_REASONING_LABEL, actor.calls[0])
        self.assertIn("t1 t2 t3", actor.calls[0])
        self.assertNotIn(OBSERVATION_LABEL, actor.calls[0])
        self.assertNotIn("LIVE_BOARD", actor.calls[0])

    def test_both_context_uses_revealed_prefix_and_live_state(self):
        observer = StubObserver([TEN_TOKEN_TRACE])
        actor = RecordingActor("S")
        env = FakeEnv([FROZEN_OBSERVATION, LIVE_OBSERVATION], done_after=2)
        _, saved, _, _ = self._run(
            observer, actor, env, context_mode="both",
        )
        self.assertIn(REVEALED_REASONING_LABEL, actor.calls[0])
        self.assertIn("t1 t2 t3", actor.calls[0])
        self.assertIn(OBSERVATION_LABEL, actor.calls[0])
        self.assertIn("FROZEN_BOARD", actor.calls[0])
        self.assertNotIn("LIVE_BOARD", actor.calls[0])
        self.assertIn("t1 t2 t3 t4 t5 t6", actor.calls[1])
        self.assertIn("LIVE_BOARD", actor.calls[1])
        self.assertNotIn("FROZEN_BOARD", actor.calls[1])
        self.assertEqual(saved["settings"]["observation_freshness"], "live")

    def test_empty_trace_does_not_invent_steps_or_rethink_forever(self):
        observer = StubObserver(["   "])
        actor = RecordingActor("S")
        env = FakeEnv([LIVE_OBSERVATION], done_after=5)
        _, saved, _, _ = self._run(
            observer, actor, env, context_mode="reasoning",
        )
        self.assertEqual(len(observer.calls), 1)
        self.assertEqual(actor.calls, [])
        self.assertEqual(saved["steps"], [])
        self.assertEqual(saved["summary"]["observer_call_count"], 1)
        self.assertIn("empty observer trace", saved["summary"]["error"])

    def test_invalid_actor_output_is_logged_as_fallback(self):
        def actor_post(endpoint, payload):
            return {"message": {"content": "Choose U"}, "done_reason": "stop"}

        actor = ActorAgent(ModelClient(ModelConfig(), post_json_fn=actor_post))
        env = FakeEnv([LIVE_OBSERVATION], done_after=1)
        _, saved, _, _ = self._run(
            RaisingObserver(), actor, env, context_mode="observation",
        )
        self.assertEqual(saved["steps"][0]["action"], "S")
        self.assertEqual(saved["steps"][0]["source"], "fallback")
        self.assertEqual(saved["steps"][0]["actor_result"]["content"], "Choose U")

    def test_success_is_terminal_u_from_player_y8(self):
        at_goal_line = {
            "state_string": "Y8",
            "game_turn": 7,
            "state": {"player_states": 8, "car_states": []},
        }
        env = FakeEnv([at_goal_line], done_after=1)
        _, saved, _, _ = self._run(
            RaisingObserver(), RecordingActor("U"), env, context_mode="observation",
        )
        self.assertTrue(saved["summary"]["success"])
        self.assertEqual(saved["summary"]["turns"], 1)
        stay_env = FakeEnv([at_goal_line], done_after=1)
        _, stay_saved, _, _ = self._run(
            RaisingObserver(), RecordingActor("S"), stay_env,
            context_mode="observation",
        )
        self.assertFalse(stay_saved["summary"]["success"])

    def test_stubbed_episode_writes_the_expected_keys(self):
        observer = StubObserver([TEN_TOKEN_TRACE])
        actor = RecordingActor("S")
        env = FakeEnv(
            [FROZEN_OBSERVATION, LIVE_OBSERVATION],
            done_after=2,
            collisions=(1,),
        )
        _, saved, _, log_path = self._run(
            observer, actor, env, context_mode="both",
        )
        self.assertTrue(log_path.exists())
        self.assertEqual(saved["environment"], "Freeway-v0")
        self.assertEqual(saved["real_seed"], 1000)
        self.assertEqual(saved["settings"]["tokenization_method"], "whitespace")
        self.assertEqual(saved["settings"]["observation_freshness"], "live")
        self.assertTrue(EXPECTED_SETTINGS_KEYS.issubset(saved["settings"]))
        self.assertEqual(len(saved["observer_cycles"]), 1)
        cycle = saved["observer_cycles"][0]
        self.assertEqual(cycle["reasoning"], TEN_TOKEN_TRACE)
        self.assertEqual(cycle["token_count"], 10)
        self.assertEqual(cycle["prefix_lengths"], [3, 6, 9, 10])
        self.assertIsNotNone(cycle["latency_seconds"])
        self.assertIn("FROZEN_BOARD", json.dumps(cycle["observation"]))
        self.assertTrue(EXPECTED_STEP_KEYS.issubset(saved["steps"][0]))
        self.assertEqual(saved["steps"][0]["collision"], True)
        self.assertEqual(saved["summary"]["collisions"], 1)
        self.assertTrue(EXPECTED_SUMMARY_KEYS.issubset(saved["summary"]))
        self.assertIsNotNone(saved["warmup"])
        self.assertEqual(saved["model_metadata"]["model"], "stub-qwen")

    def test_log_is_written_when_metadata_fetch_fails(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        log_path = Path(directory) / "fail.json"
        runner = ExperimentRunner(
            RaisingObserver(),
            RecordingActor(),
            _args(str(log_path), context_mode="observation"),
        )

        def boom(endpoint, payload):
            raise ConnectionError("ollama down")

        with patch(
            "decision_model_experiments.experiment_runner.post_json",
            boom,
        ):
            with self.assertRaises(ConnectionError):
                runner.run()
        saved = json.loads(log_path.read_text())
        self.assertIn("ConnectionError", saved["summary"]["error"])
        self.assertEqual(saved["steps"], [])
        self.assertEqual(saved["observer_cycles"], [])


class RealtimeGymSmokeTests(unittest.TestCase):
    def test_runner_reset_step_against_realtimegym(self):
        try:
            import realtimegym
        except ImportError as exc:
            self.fail(f"RealtimeGym must be installed for this smoke test: {exc}")

        class BoundedEnv:
            def __init__(self, env, max_turns=2):
                self._env = env
                self.max_turns = max_turns

            def reset(self):
                return self._env.reset()

            def step(self, action):
                observation, done, score, collided = self._env.step(action)
                if self._env.game_turn >= self.max_turns:
                    done = True
                return observation, done, score, collided

            def summary(self):
                return self._env.summary()

            @property
            def game_turn(self):
                return self._env.game_turn

            @property
            def reward(self):
                return self._env.reward

        real_env, real_seed, _ = realtimegym.make(
            "Freeway-v0", seed=0, render=False,
        )
        observation, done = real_env.reset()
        self.assertFalse(done)
        self.assertIn("state", observation)
        observation, done, score, collided = real_env.step("S")
        self.assertIn("state", observation)
        self.assertEqual(int(real_env.game_turn), 1)

        directory = self.enterContext(tempfile.TemporaryDirectory())
        log_path = Path(directory) / "realtimegym.json"
        actor = RecordingActor("S")
        runner = ExperimentRunner(
            RaisingObserver(),
            actor,
            _args(str(log_path), context_mode="observation"),
        )

        def fake_post(endpoint, payload):
            if endpoint == "show":
                return {"model": "stub-qwen"}
            return {"message": {"content": "S"}, "done_reason": "stop"}

        def make_bounded(seed):
            env, mapped_seed, renderer = realtimegym.make(
                "Freeway-v0", seed=seed, render=False,
            )
            return BoundedEnv(env), mapped_seed, renderer

        with patch(
            "decision_model_experiments.experiment_runner.post_json",
            fake_post,
        ), patch(
            "decision_model_experiments.experiment_runner._make_freeway",
            make_bounded,
        ):
            episode = runner.run()
        self.assertEqual(len(actor.calls), 2)
        self.assertEqual(len(episode["steps"]), 2)
        self.assertEqual(episode["observer_cycles"], [])
        self.assertEqual(episode["real_seed"], int(real_seed))
        self.assertIn("state", episode["initial_observation"])
        self.assertTrue(episode["steps"][-1]["done"])
        self.assertEqual(episode["summary"]["observer_call_count"], 0)


if __name__ == "__main__":
    unittest.main()
