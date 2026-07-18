"""Generic OpenAI-compatible endpoint adapter.

This adapter is intended for customer-owned or self-hosted endpoints that
implement the OpenAI-compatible /v1 API surface.

Environment variables:
- GENERIC_OPENAI_API_URL: base URL, for example http://localhost:11434/v1
- GENERIC_OPENAI_API_KEY: API key if required by the endpoint
- GENERIC_OPENAI_DEFAULT_MODEL: model name to use
"""

from __future__ import annotations

import os

from .base import BaseLLMAdapter


class GenericOpenAICompatibleAdapter(BaseLLMAdapter):
    """Adapter for any OpenAI-compatible endpoint configured by the customer."""

    @property
    def provider_name(self) -> str:
        return "Generic OpenAI Compatible"

    @property
    def default_model(self) -> str:
        return os.environ.get("GENERIC_OPENAI_DEFAULT_MODEL", "gpt-compatible")

    @property
    def base_url(self) -> str:
        return os.environ.get("GENERIC_OPENAI_API_URL", "").strip()

    @property
    def api_key(self) -> str:
        return os.environ.get("GENERIC_OPENAI_API_KEY", "").strip()

    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def is_available(self) -> bool:
        if not self.is_configured():
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
        if not self.is_configured():
            raise RuntimeError("Generic OpenAI-compatible adapter is not configured: GENERIC_OPENAI_API_URL is not set")

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
