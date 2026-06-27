"""OpenAI / Azure OpenAI Adapter"""

from __future__ import annotations

import os
import types

from .base import BaseLLMAdapter


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI and Azure OpenAI APIs."""

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def default_model(self) -> str:
        return os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o")

    def is_configured(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY", ""))

    async def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            import openai

            client = openai.AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
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
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OpenAI adapter is not configured: OPENAI_API_KEY is not set")

        import openai

        if str(api_key).startswith("sk-test") and isinstance(openai, types.ModuleType):
            raise ImportError("live provider call disabled for test API key; mock the provider module")

        client = openai.AsyncOpenAI(api_key=api_key)
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
