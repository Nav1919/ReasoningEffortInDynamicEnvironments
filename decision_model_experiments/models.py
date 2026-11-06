"""Call local LLMs.

- call_reasoning_model: Qwen via Ollama (default `qwen3:4b-q4_K_M`); thinking on by default
- call_instant_model: same Ollama chat path and frozen tag; thinking off by default

Tests: `python -m unittest tests.test_decision_models -v`
"""

import json
import time
from dataclasses import dataclass
from urllib.request import Request, urlopen


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_REASONING_MODEL = "qwen3:4b-q4_K_M"


def post_json(endpoint, payload, host=DEFAULT_HOST, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    # Same local Ollama POST as run_model_freeway.py, with an explicit host so
    # tests can inject a fake transport without starting a server.
    request = Request(
        f"{host.rstrip('/')}/api/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_action(response, error=None):
    # Accept only a completed response containing one action, ignoring case
    # and surrounding whitespace. Never extract actions from prose or thinking.
    content = (response or {}).get("message", {}).get("content", "")
    action = content.strip().upper()
    valid = (error is None and (response or {}).get("done_reason") == "stop"
             and action in {"U", "D", "S"})
    return action if valid else None


@dataclass(frozen=True)
class ModelConfig:
    """Connection and sampling settings for local model calls."""

    reasoning_model: str = DEFAULT_REASONING_MODEL
    seed: int = 0
    temperature: float = 0.6
    num_ctx: int = 4096
    host: str = DEFAULT_HOST
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    keep_alive: str = "5m"


@dataclass(frozen=True)
class GenerationResult:
    """One model call, including failed requests that must be logged."""

    prompt: str
    max_tokens: int
    think: bool
    payload: dict
    response: dict | None
    error: str | None
    content: str
    thinking: str
    done_reason: str | None
    output_tokens: int | None
    input_tokens: int | None
    latency_seconds: float


class ModelClient:
    def __init__(self, config=None, post_json_fn=None):
        self.config = config or ModelConfig()
        self._post_json = post_json_fn or self._post_to_configured_host

    def _post_to_configured_host(self, endpoint, payload):
        return post_json(
            endpoint,
            payload,
            host=self.config.host,
            timeout_seconds=self.config.timeout_seconds,
        )

    def _build_chat_payload(self, model, prompt, max_tokens, think):
        if max_tokens <= 0:
            raise ValueError("max_tokens must be a positive token count")
        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "think": think,
            "stream": False,
            "keep_alive": self.config.keep_alive,
            "options": {
                "temperature": self.config.temperature,
                "seed": self.config.seed,
                "num_predict": max_tokens,
                "num_ctx": self.config.num_ctx,
            },
        }

    def _call_chat(self, model, prompt, max_tokens, think):
        # One Ollama /api/chat round-trip for both the reasoning and instant
        # models. Failures stay in GenerationResult so the runner can log them.
        payload = self._build_chat_payload(model, prompt, max_tokens, think)
        started = time.perf_counter()
        try:
            response = self._post_json("chat", payload)
            error = None
        except Exception as exception:
            response = None
            error = f"{type(exception).__name__}: {exception}"
        latency_seconds = time.perf_counter() - started
        message = (response or {}).get("message") or {}
        return GenerationResult(
            prompt=prompt,
            max_tokens=max_tokens,
            think=bool(think),
            payload=payload,
            response=response,
            error=error,
            content=message.get("content") or "",
            thinking=message.get("thinking") or "",
            done_reason=(response or {}).get("done_reason"),
            output_tokens=(response or {}).get("eval_count"),
            input_tokens=(response or {}).get("prompt_eval_count"),
            latency_seconds=latency_seconds,
        )

    def call_reasoning_model(self, prompt, max_tokens, think=True):
        return self._call_chat(
            self.config.reasoning_model, prompt, max_tokens, think,
        )

    def call_instant_model(self, prompt, max_tokens, think=False):
        # Same frozen Qwen tag as the observer. Thinking stays off unless a
        # later experiment explicitly asks the instant model to reason.
        return self._call_chat(
            self.config.reasoning_model, prompt, max_tokens, think,
        )
    
    def call_decision_model(self, prompt, categories):
        # Do not change this, will be implemented later
        pass
