# Offline checks for the actor prompt, strict parse, and fallback S.
# They stub the model client and do not call Ollama.
import inspect
import unittest

from decision_model_experiments.actor_agent import (
    FALLBACK_ACTION,
    ActorAgent,
    build_actor_prompt,
)
from decision_model_experiments.models import (
    DEFAULT_REASONING_MODEL,
    GenerationResult,
    ModelClient,
    ModelConfig,
)


SAMPLE_CONTEXT = "lane 1 is empty; player_states is 0"


def _actor(post_json_fn, **kwargs):
    client = ModelClient(ModelConfig(), post_json_fn=post_json_fn)
    return ActorAgent(client, **kwargs)


class ActorPromptTests(unittest.TestCase):
    def test_prompt_includes_context_and_asks_for_an_action_letter(self):
        prompt = build_actor_prompt(SAMPLE_CONTEXT)
        self.assertIn(SAMPLE_CONTEXT, prompt)
        self.assertIn("Choose one action", prompt)
        self.assertIn("Return only U, D, or S", prompt)
        self.assertNotIn("context_mode", prompt)
        self.assertNotIn("Write reasoning only", prompt)
        self.assertNotIn("do not choose an action letter", prompt)

    def test_prompt_does_not_name_experimental_modes(self):
        instructions = build_actor_prompt("lane 1 is empty").split("Context:")[0]
        for mode_name in ("reasoning", "observation", "both"):
            self.assertNotIn(mode_name, instructions)


class ActorActTests(unittest.TestCase):
    def test_act_does_not_take_context_mode(self):
        self.assertEqual(list(inspect.signature(ActorAgent.act).parameters), ["self", "context"])
        self.assertNotIn("context_mode", inspect.signature(ActorAgent.__init__).parameters)

    def test_act_calls_instant_model_with_thinking_off(self):
        captured = {}

        def fake_post(endpoint, payload):
            captured["endpoint"] = endpoint
            captured["payload"] = payload
            return {
                "message": {"content": "U", "thinking": ""},
                "done_reason": "stop",
                "eval_count": 1,
                "prompt_eval_count": 12,
            }

        actor = _actor(fake_post, max_tokens=8)
        action = actor.act(SAMPLE_CONTEXT)
        payload = captured["payload"]
        self.assertEqual(action, "U")
        self.assertEqual(actor.last_action_source, "actor")
        self.assertEqual(captured["endpoint"], "chat")
        self.assertEqual(payload["model"], DEFAULT_REASONING_MODEL)
        self.assertEqual(payload["think"], False)
        self.assertEqual(payload["options"]["num_predict"], 8)
        self.assertIn(SAMPLE_CONTEXT, payload["messages"][0]["content"])
        self.assertIn("Return only U, D, or S", payload["messages"][0]["content"])
        self.assertIsInstance(actor.last_result, GenerationResult)
        self.assertEqual(actor.last_result.content, "U")
        self.assertFalse(actor.last_result.think)
        self.assertIsNone(actor.last_result.error)

    def test_prose_is_a_failure_plus_fallback_s(self):
        def fake_post(endpoint, payload):
            return {"message": {"content": "Choose U"}, "done_reason": "stop"}

        actor = _actor(fake_post)
        self.assertEqual(actor.act(SAMPLE_CONTEXT), FALLBACK_ACTION)
        self.assertEqual(actor.last_action_source, "fallback")
        self.assertEqual(actor.last_result.content, "Choose U")

    def test_truncated_output_is_a_failure_plus_fallback_s(self):
        def fake_post(endpoint, payload):
            return {"message": {"content": "U"}, "done_reason": "length"}

        actor = _actor(fake_post)
        self.assertEqual(actor.act(SAMPLE_CONTEXT), FALLBACK_ACTION)
        self.assertEqual(actor.last_action_source, "fallback")

    def test_failed_request_is_kept_and_falls_back_to_s(self):
        def boom(endpoint, payload):
            raise TimeoutError("slow")

        actor = _actor(boom)
        self.assertEqual(actor.act(SAMPLE_CONTEXT), FALLBACK_ACTION)
        self.assertEqual(actor.last_action_source, "fallback")
        self.assertEqual(actor.last_result.content, "")
        self.assertIsNone(actor.last_result.response)
        self.assertIn("TimeoutError", actor.last_result.error)


if __name__ == "__main__":
    unittest.main()
