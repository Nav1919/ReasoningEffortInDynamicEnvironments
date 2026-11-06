# Offline checks for the observer prompt and think() call.
# They stub the model client and do not call Ollama.
import copy
import unittest

from decision_model_experiments.models import (
    GenerationResult,
    ModelClient,
    ModelConfig,
)
from decision_model_experiments.observer_agent import (
    ObserverAgent,
    build_observer_prompt,
)


SAMPLE_OBSERVATION = {
    "state_string": "BOARD_MARKER",
    "game_turn": 0,
    "state": {"player_states": 0, "car_states": []},
}


def _observer(post_json_fn, max_tokens=8, **kwargs):
    client = ModelClient(ModelConfig(), post_json_fn=post_json_fn)
    return ObserverAgent(client, max_tokens=max_tokens, **kwargs)


class ObserverPromptTests(unittest.TestCase):
    def test_prompt_includes_observation_and_asks_for_reasoning_only(self):
        prompt = build_observer_prompt(SAMPLE_OBSERVATION)
        self.assertIn("BOARD_MARKER", prompt)
        self.assertIn('"player_states": 0', prompt)
        self.assertIn("do not choose an action letter", prompt)
        self.assertIn("Write reasoning only", prompt)
        self.assertNotIn("Choose one action", prompt)
        self.assertNotIn("Return only U, D, or S", prompt)

    def test_structured_board_drops_the_text_drawing_only(self):
        saved = copy.deepcopy(SAMPLE_OBSERVATION)
        full = build_observer_prompt(SAMPLE_OBSERVATION, board="full")
        structured = build_observer_prompt(SAMPLE_OBSERVATION, board="structured")
        self.assertIn("BOARD_MARKER", full)
        self.assertNotIn("BOARD_MARKER", structured)
        self.assertIn('"player_states": 0', structured)
        self.assertEqual(full.split("Observation:")[0], structured.split("Observation:")[0])
        self.assertEqual(SAMPLE_OBSERVATION, saved)


class ObserverThinkTests(unittest.TestCase):
    def test_think_calls_reasoning_model_with_budget_and_thinking_on(self):
        captured = {}

        def fake_post(endpoint, payload):
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            return {
                "message": {"content": "lane 1 is clear", "thinking": "scan cars"},
                "done_reason": "stop",
                "eval_count": 4,
                "prompt_eval_count": 20,
            }

        observer = _observer(fake_post, max_tokens=10)
        text = observer.think(SAMPLE_OBSERVATION)
        payload = captured["payload"]
        self.assertEqual(text, "lane 1 is clear")
        self.assertEqual(captured["endpoint"], "chat")
        self.assertEqual(payload["think"], True)
        self.assertEqual(payload["options"]["num_predict"], 10)
        self.assertIn("BOARD_MARKER", payload["messages"][0]["content"])
        self.assertIn("do not choose an action letter", payload["messages"][0]["content"])
        self.assertIsInstance(observer.last_result, GenerationResult)
        self.assertEqual(observer.last_result.content, text)
        self.assertEqual(observer.last_result.thinking, "scan cars")
        self.assertEqual(observer.last_result.output_tokens, 4)
        self.assertIsNone(observer.last_result.error)

    def test_think_returns_action_letters_as_plain_text(self):
        # The observer must not treat U as an environment action.
        def fake_post(endpoint, payload):
            return {"message": {"content": "U"}, "done_reason": "stop"}

        observer = _observer(fake_post)
        self.assertEqual(observer.think(SAMPLE_OBSERVATION), "U")
        self.assertEqual(observer.last_result.content, "U")

    def test_failed_request_is_kept(self):
        def boom(endpoint, payload):
            raise TimeoutError("slow")

        observer = _observer(boom)
        text = observer.think(SAMPLE_OBSERVATION)
        self.assertEqual(text, "")
        self.assertIsNone(observer.last_result.response)
        self.assertIn("TimeoutError", observer.last_result.error)


if __name__ == "__main__":
    unittest.main()
