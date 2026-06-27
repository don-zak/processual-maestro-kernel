"""DeepSeek Adapter

Uses OpenAI-compatible API format (DeepSeek API is OpenAI-compatible).
"""

from __future__ import annotations

import os
import types

from .base import BaseLLMAdapter


class DeepSeekAdapter(BaseLLMAdapter):
    """Adapter for DeepSeek API (OpenAI-compatible)."""

    BASE_URL = "https://api.deepseek.com/v1"

    @property
    def provider_name(self) -> str:
        return "DeepSeek"

    @property
    def default_model(self) -> str:
        return os.environ.get("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat")

    def is_configured(self) -> bool:
        return bool(os.environ.get("DEEPSEEK_API_KEY", ""))

    async def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            api_key = os.environ.get("DEEPSEEK_API_KEY") or ""
            import openai

            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url=self.BASE_URL,
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
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DeepSeek adapter is not configured: DEEPSEEK_API_KEY is not set")

        import openai

        if str(api_key).startswith("ds-test") and isinstance(openai, types.ModuleType):
            raise ImportError("live provider call disabled for test API key; mock the provider module")

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self.BASE_URL,
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
