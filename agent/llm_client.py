"""LLM client supporting multiple providers (OpenAI-compatible API)."""

import json
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from agent.config import Config


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str
    latency_s: float
    stop_reason: str = "stop"


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Session:
    """Tracks token usage across a run."""
    messages: list[Message] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    run_count: int = 0

    def add_message(self, role: str, content: str):
        self.messages.append(Message(role=role, content=content))

    def add_turn(self, tokens_in: int, tokens_out: int, cost: float):
        self.total_tokens += tokens_in + tokens_out
        self.total_cost += cost
        self.run_count += 1


PROVIDER_URLS = {
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "anthropic": "https://api.anthropic.com/v1/messages",
}


class LLMClient:
    """Multi-provider LLM client using OpenAI-compatible endpoints."""

    def __init__(self, config: Config):
        self.config = config
        self.session = Session()
        self._api_key = config.llm.get_api_key()
        self._base_url = self._get_base_url()
        self._model = config.llm.model

        # Headers per provider
        if config.llm.provider == "anthropic":
            self._headers = {
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        else:
            self._headers = {
                "Authorization": f"Bearer {self._api_key}",
                "content-type": "application/json",
            }

        # Set OpenRouter app header if applicable
        if config.llm.provider == "openrouter":
            self._headers["HTTP-Referer"] = "https://evo-garden.local"
            self._headers["X-Title"] = "Evo Garden Agent"

    def _get_base_url(self) -> str:
        provider = self.config.llm.provider
        # Provider-specific endpoint or custom URL
        if self.config.llm.api_url and self.config.llm.api_url != "https://openrouter.ai/api/v1":
            return self.config.llm.api_url
        return PROVIDER_URLS.get(provider, self.config.llm.api_url)

    def chat(
        self,
        system: str = "",
        messages: list[Message] | list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request."""
        start = time.time()

        if messages is None:
            messages = []

        # Build request payload
        if self.config.llm.provider == "anthropic":
            payload = self._build_anthropic_payload(system, messages, max_tokens, temperature)
            url = f"{self.config.llm.api_url or PROVIDER_URLS['anthropic']}"
            headers = self._headers
        else:
            payload = self._build_openai_payload(system, messages, max_tokens, temperature)
            url = f"{self._base_url}" if self._base_url.endswith("/chat/completions") else f"{self._base_url}/chat/completions"
            headers = self._headers

        resp = httpx.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        # Parse response (OpenAI format)
        if self.config.llm.provider == "anthropic":
            content = data.get("content", [{}])[0].get("text", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
        else:
            choices = data.get("choices", [{}])
            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

        total = input_tokens + output_tokens
        cost = self._estimate_cost(input_tokens, output_tokens)
        latency = time.time() - start

        self.session.add_turn(input_tokens, output_tokens, cost)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            model=self._model,
            latency_s=latency,
            stop_reason=data.get("choices", [{}])[0].get("finish_reason", "stop"),
        )

    def _build_openai_payload(self, system, messages, max_tokens, temperature):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        for m in messages:
            if isinstance(m, Message):
                msgs.append({"role": m.role, "content": m.content})
            else:
                msgs.append(m)
        return {
            "model": self._model,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    def _build_anthropic_payload(self, system, messages, max_tokens, temperature):
        msgs = []
        for m in messages:
            if isinstance(m, Message):
                msgs.append({"role": m.role, "content": m.content})
            else:
                msgs.append(m)
        return {
            "model": self._model,
            "system": system,
            "messages": msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Rough cost estimates per 1M tokens (USD)."""
        # Default mid-tier model pricing
        input_cost = 0.25  # per 1M tokens
        output_cost = 0.75  # per 1M tokens

        model = self._model.lower()
        if "opus" in model or "claude-3-opus" in model:
            input_cost, output_cost = 15.0, 75.0
        elif "sonnet" in model or "claude-3-sonnet" in model:
            input_cost, output_cost = 3.0, 15.0
        elif "gemini" in model:
            input_cost, output_cost = 0.35, 1.05
        elif "llama-3" in model or "llama-3.1" in model:
            input_cost, output_cost = 0.20, 0.20
        elif "gpt-4o" in model:
            input_cost, output_cost = 5.0, 15.0
        elif "gpt-4" in model and "mini" not in model:
            input_cost, output_cost = 10.0, 30.0
        elif "mini" in model:
            input_cost, output_cost = 0.15, 0.60

        return (input_tokens / 1_000_000 * input_cost) + (output_tokens / 1_000_000 * output_cost)
