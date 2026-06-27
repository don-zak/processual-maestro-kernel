"""OpenCode / OpenAI-Compatible Local Endpoint Adapter

This adapter connects to any OpenAI-compatible API endpoint:
- Ollama (http://localhost:11434/v1)
- vLLM (http://localhost:8000/v1)
- LocalAI (http://localhost:8080/v1)
- OpenCode API (if exposed)
- Any OpenAI-compatible proxy

The user configures:
- OPENCODE_API_URL: base URL of the OpenAI-compatible endpoint
- OPENCODE_API_KEY: API key (if required)
- OPENCODE_DEFAULT_MODEL: model name to use
"""

from __future__ import annotations

import os

from .base import BaseLLMAdapter


class OpenCodeAdapter(BaseLLMAdapter):
    """Adapter for any OpenAI-compatible endpoint (local or self-hosted)."""

    @property
    def provider_name(self) -> str:
        return "OpenCode"

    @property
    def default_model(self) -> str:
        return os.environ.get("OPENCODE_DEFAULT_MODEL", "llama3")

    @property
    def base_url(self) -> str:
        return os.environ.get("OPENCODE_API_URL", "http://localhost:11434/v1")

    @property
    def api_key(self) -> str:
        return os.environ.get("OPENCODE_API_KEY", "")

    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def is_available(self) -> bool:
        # The default localhost URL is enough for configuration discovery,
        # but availability must not attempt a live network call unless the
        # endpoint was explicitly configured. This keeps tests and offline
        # environments deterministic.
        if not self.is_configured() or "OPENCODE_API_URL" not in os.environ:
            return False
        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=self.api_key or "sk-placeholder",
                base_url=self.base_url,
            )
            await client.models.list()
            return True
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        import openai

        client = openai.AsyncOpenAI(
            api_key=self.api_key or "sk-placeholder",
            base_url=self.base_url,
        )
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model = kwargs.get("model") or self.default_model
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
        )
        return response.choices[0].message.content or ""
