# Offline checks for the shared model client.
# They do not call Ollama and cannot be mistaken for episode performance.
import unittest

from decision_model_experiments.models import (
    DEFAULT_REASONING_MODEL,
    ModelClient,
    ModelConfig,
    parse_action,
)


def _client(config=None, post_json_fn=None):
    return ModelClient(config or ModelConfig(), post_json_fn=post_json_fn)


class ParseActionTests(unittest.TestCase):
    def test_only_complete_single_actions_are_accepted(self):
        # Copied from test_model_freeway.py so the shared parser stays strict.
        for text, reason, expected in [
            ("U", "stop", "U"), (" d\n", "stop", "D"), ("S", "stop", "S"),
            ("Choose U", "stop", None), ("U S", "stop", None),
            ("U", "length", None), ("", "stop", None),
        ]:
            with self.subTest(text=text, reason=reason):
                response = {"message": {"content": text, "thinking": "U"},
                            "done_reason": reason}
                self.assertEqual(parse_action(response), expected)
        self.assertIsNone(parse_action(None, "HTTP failed"))


class ReasoningModelTests(unittest.TestCase):
    def test_default_model_is_qwen_reasoning(self):
        captured = {}

        def fake_post(endpoint, payload):
            captured["payload"] = payload
            return {"message": {"content": "S"}, "done_reason": "stop"}

        _client(post_json_fn=fake_post).call_reasoning_model(
            "Return only S.", max_tokens=8,
        )
        self.assertEqual(captured["payload"]["model"], DEFAULT_REASONING_MODEL)
        self.assertEqual(DEFAULT_REASONING_MODEL, "qwen3:4b-q4_K_M")

    def test_payload_copies_frozen_sampling_fields(self):
        captured = {}

        def fake_post(endpoint, payload):
            captured["payload"] = payload
            return {"message": {"content": "S"}, "done_reason": "stop"}

        _client(
            ModelConfig(seed=7, temperature=0.6, num_ctx=4096),
            post_json_fn=fake_post,
        ).call_reasoning_model("Return only S.", max_tokens=8, think=True)
        payload = captured["payload"]
        self.assertEqual(payload["think"], True)
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["options"]["seed"], 7)
        self.assertEqual(payload["options"]["temperature"], 0.6)
        self.assertEqual(payload["options"]["num_predict"], 8)
        self.assertEqual(payload["options"]["num_ctx"], 4096)

    def test_call_records_failed_requests(self):
        def boom(endpoint, payload):
            raise TimeoutError("slow")

        result = _client(post_json_fn=boom).call_reasoning_model(
            "Return only U.", max_tokens=4,
        )
        self.assertIsNone(result.response)
        self.assertEqual(result.content, "")
        self.assertIn("TimeoutError", result.error)

    def test_call_extracts_chat_fields(self):
        def fake_post(endpoint, payload):
            self.assertEqual(endpoint, "chat")
            self.assertEqual(payload["model"], DEFAULT_REASONING_MODEL)
            return {
                "message": {"content": "U", "thinking": ""},
                "done_reason": "stop",
                "eval_count": 1,
                "prompt_eval_count": 6,
            }

        result = _client(post_json_fn=fake_post).call_reasoning_model(
            "Return only U.", max_tokens=4,
        )
        self.assertEqual(result.content, "U")
        self.assertIsNone(result.error)
        self.assertEqual(result.output_tokens, 1)
        self.assertEqual(parse_action(result.response, result.error), "U")


class InstantModelTests(unittest.TestCase):
    def test_default_model_is_the_same_frozen_qwen(self):
        captured = {}

        def fake_post(endpoint, payload):
            captured["payload"] = payload
            return {"message": {"content": "S"}, "done_reason": "stop"}

        _client(post_json_fn=fake_post).call_instant_model(
            "Return only S.", max_tokens=8,
        )
        self.assertEqual(captured["payload"]["model"], DEFAULT_REASONING_MODEL)
        self.assertEqual(captured["payload"]["think"], False)
        self.assertEqual(DEFAULT_REASONING_MODEL, "qwen3:4b-q4_K_M")

    def test_payload_copies_frozen_sampling_fields(self):
        captured = {}

        def fake_post(endpoint, payload):
            captured["payload"] = payload
            return {"message": {"content": "U"}, "done_reason": "stop"}

        _client(
            ModelConfig(seed=7, temperature=0.6, num_ctx=4096),
            post_json_fn=fake_post,
        ).call_instant_model("Return only U.", max_tokens=4)
        payload = captured["payload"]
        self.assertEqual(payload["think"], False)
        self.assertEqual(payload["stream"], False)
        self.assertEqual(payload["options"]["seed"], 7)
        self.assertEqual(payload["options"]["temperature"], 0.6)
        self.assertEqual(payload["options"]["num_predict"], 4)
        self.assertEqual(payload["options"]["num_ctx"], 4096)

    def test_call_records_failed_requests(self):
        def boom(endpoint, payload):
            raise TimeoutError("slow")

        result = _client(post_json_fn=boom).call_instant_model(
            "Return only U.", max_tokens=4,
        )
        self.assertIsNone(result.response)
        self.assertEqual(result.content, "")
        self.assertIn("TimeoutError", result.error)
        self.assertIsNone(parse_action(result.response, result.error))

    def test_call_extracts_chat_fields(self):
        def fake_post(endpoint, payload):
            self.assertEqual(endpoint, "chat")
            self.assertEqual(payload["model"], DEFAULT_REASONING_MODEL)
            self.assertEqual(payload["think"], False)
            return {
                "message": {"content": "U", "thinking": ""},
                "done_reason": "stop",
                "eval_count": 1,
                "prompt_eval_count": 6,
            }

        result = _client(post_json_fn=fake_post).call_instant_model(
            "Return only U.", max_tokens=4,
        )
        self.assertEqual(result.content, "U")
        self.assertFalse(result.think)
        self.assertIsNone(result.error)
        self.assertEqual(result.output_tokens, 1)
        self.assertEqual(parse_action(result.response, result.error), "U")


if __name__ == "__main__":
    unittest.main()
