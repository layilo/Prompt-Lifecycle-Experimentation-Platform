from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class ModelResponse:
    output: Any
    latency_ms: float
    tokens_in: int
    tokens_out: int
    cost: float
    structured_valid: bool = True


class ModelClient(Protocol):
    def generate(self, prompt_text: str, task_type: str, inputs: dict[str, Any], **kwargs: Any) -> ModelResponse:
        ...


class MockModelClient:
    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    def generate(self, prompt_text: str, task_type: str, inputs: dict[str, Any], **kwargs: Any) -> ModelResponse:
        text = json.dumps(inputs, sort_keys=True)
        base_latency = 40 + (len(prompt_text) % 10) + self.seed
        tokens_in = max(8, len(prompt_text.split()) + len(text.split()))
        if task_type == "classification":
            message = inputs.get("customer_message", "").lower()
            if "charged" in message or "refund" in message or "invoice" in message:
                output = "billing"
            elif "crash" in message or "bug" in message or "upload" in message:
                output = "technical"
            elif "password" in message or "login" in message or "cancel" in message:
                output = "account"
            else:
                output = "shipping"
        elif task_type == "summarization":
            doc = inputs.get("document", "")
            output = ". ".join(sentence.strip() for sentence in doc.split(".") if sentence.strip()[:60])[:220]
        elif task_type == "extraction":
            output = {"fields": inputs}
        elif task_type == "qa":
            output = inputs.get("question", "")
        else:
            output = json.dumps(inputs, sort_keys=True)
        tokens_out = max(4, len(str(output).split()))
        cost = tokens_in * 0.000001 + tokens_out * 0.000002
        return ModelResponse(output=output, latency_ms=float(base_latency), tokens_in=tokens_in, tokens_out=tokens_out, cost=cost)


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key_env: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = os.getenv(api_key_env, "")
        self.model = model

    def generate(self, prompt_text: str, task_type: str, inputs: dict[str, Any], **kwargs: Any) -> ModelResponse:
        if not self.api_key:
            raise RuntimeError("Missing API key for OpenAI-compatible backend")
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt_text}],
            **kwargs,
        }
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        return ModelResponse(
            output=content,
            latency_ms=0.0,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            cost=0.0,
            structured_valid=True,
        )


def build_model_client(backend: str, config: dict[str, Any], model: str = "mock-model") -> ModelClient:
    provider = config.get("provider", "mock")
    if provider == "mock":
        return MockModelClient(seed=int(config.get("seed", 0)))
    if provider == "openai-compatible":
        return OpenAICompatibleClient(
            base_url=config["base_url"],
            api_key_env=config["api_key_env"],
            model=model,
        )
    raise ValueError(f"Unsupported provider: {provider}")

