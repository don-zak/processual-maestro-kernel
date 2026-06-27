"""OpenRouter / OpenAI-Compatible Adapter

This adapter connects Processual Maestro to OpenRouter through its
OpenAI-compatible API endpoint.

Environment variables:
- OPENROUTER_API_URL: OpenRouter base URL
- OPENROUTER_API_KEY: OpenRouter API key
- OPENROUTER_DEFAULT_MODEL: model slug to use
"""

from __future__ import annotations

import os

from .base import BaseLLMAdapter


class OpenRouterAdapter(BaseLLMAdapter):
    """Adapter for OpenRouter OpenAI-compatible endpoint."""

    @property
    def provider_name(self) -> str:
        return "OpenRouter"

    @property
    def default_model(self) -> str:
        return os.environ.get("OPENROUTER_DEFAULT_MODEL", "openrouter/free")

    @property
    def base_url(self) -> str:
        return os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1")

    @property
    def api_key(self) -> str:
        return os.environ.get("OPENROUTER_API_KEY", "")

    def is_configured(self) -> bool:
        api_key = self.api_key.strip()
        return bool(api_key) and "Ø¶Ø¹_" not in api_key and "YOUR_" not in api_key

    def _default_headers(self) -> dict[str, str]:
        return {
            "HTTP-Referer": os.environ.get("OPENROUTER_HTTP_REFERER", "http://127.0.0.1:8000"),
            "X-Title": os.environ.get("OPENROUTER_APP_TITLE", "Processual Maestro Kernel"),
        }

    async def is_available(self) -> bool:
        if not self.is_configured():
            return False

        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                default_headers=self._default_headers(),
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
            raise RuntimeError("OpenRouter adapter is not configured: OPENROUTER_API_KEY is not set")

        import openai

        client = openai.AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            default_headers=self._default_headers(),
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
