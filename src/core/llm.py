"""LLM Provider — multi-provider abstraction for GitPup AI reasoning.

Supports OpenAI, OpenRouter, Groq. All use OpenAI-compatible API.
All API keys via env vars only — never committed.
"""

import os
import json
from typing import Optional
from openai import OpenAI


class LLMProvider:
    """Unified LLM interface across providers."""

    PROVIDERS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "model_env": "OPENAI_MODEL",
            "default_model": "gpt-4o-mini",
            "key_env": "OPENAI_API_KEY",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "model_env": "OPENROUTER_MODEL",
            "default_model": "openai/gpt-4o-mini",
            "key_env": "OPENROUTER_API_KEY",
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "model_env": "GROQ_MODEL",
            "default_model": "llama-3.3-70b-versatile",
            "key_env": "GROQ_API_KEY",
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1/messages",
            "model_env": "ANTHROPIC_MODEL",
            "default_model": "claude-sonnet-4-20250514",
            "key_env": "ANTHROPIC_API_KEY",
        },
        "local": {
            "base_url": "http://localhost:8080/v1",
            "model_env": "LOCAL_MODEL",
            "default_model": "local-model",
            "key_env": "LOCAL_API_KEY",
        },
    }

    def __init__(self, provider: Optional[str] = None):
        self.name = provider or os.getenv("LLM_PROVIDER", "openai").lower()
        if self.name not in self.PROVIDERS:
            raise ValueError(
                f"Unknown LLM provider: {self.name}. "
                f"Choose from {list(self.PROVIDERS.keys())}"
            )

        config = self.PROVIDERS[self.name]
        self.api_key = os.getenv(config["key_env"], "")
        self.model = os.getenv(config["model_env"], config["default_model"])

        if not self.api_key:
            raise EnvironmentError(
                f"API key not set for {self.name}. "
                f"Set {config['key_env']} in .env (NEVER commit to gitlawb!)"
            )

        self.base_url = config["base_url"]
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url if self.name != "anthropic" else None,
        )

    def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Send chat messages and get response."""
        if self.name == "anthropic":
            return self._chat_anthropic_raw(messages, temperature, max_tokens)

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def _chat_anthropic_raw(self, messages: list[dict], temperature: float, max_tokens: int) -> str:
        """Call Anthropic API directly via HTTP (no extra SDK needed)."""
        import httpx

        system_msg = ""
        chat_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                chat_msgs.append(m)

        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_msgs,
        }
        if system_msg:
            body["system"] = system_msg

        resp = httpx.post(
            self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("content", [{}])[0].get("text", "")

    def summarize_code(self, code: str, language: str = "python") -> str:
        """Summarize a code file."""
        system = (
            "You are GitPup, a golden retriever AI agent. "
            "You analyze code and give clear, friendly summaries. "
            "Use emojis and keep it concise. Always bark at the end 🐕"
        )
        user = (
            f"Summarize this {language} code. Focus on:\n"
            f"1. What does this code do?\n"
            f"2. Key functions/classes\n"
            f"3. Any issues or improvements\n\n"
            f"Code:\n```{language}\n{code[:8000]}\n```"
        )
        return self.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ])

    def review_pr(self, diff: str, context: str = "") -> str:
        """Review a pull request diff."""
        system = (
            "You are GitPup, a golden retriever code reviewer. "
            "You review PR diffs and give constructive feedback. "
            "Be thorough but friendly. Point out bugs, security issues, "
            "and suggest improvements. Give a score /100. 🐾"
        )
        user = f"{context}\n\nPR diff:\n```diff\n{diff[:10000]}\n```"
        return self.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], max_tokens=4096)

    def write_docs(self, topic: str, context: str = "") -> str:
        """Generate documentation."""
        system = (
            "You are GitPup, a golden retriever technical writer. "
            "Write clear, helpful documentation in markdown format. 🐶"
        )
        user = f"{context}\n\nWrite documentation about: {topic}"
        return self.chat([
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ], max_tokens=4096)

    def is_available(self) -> bool:
        """Check if LLM provider is configured."""
        return bool(self.api_key) and len(self.api_key) > 10


def get_provider() -> Optional["LLMProvider"]:
    """Get LLM provider from env, return None if not configured."""
    provider_name = os.getenv("LLM_PROVIDER", "openai").lower()
    try:
        return LLMProvider(provider_name)
    except Exception:
        return None
