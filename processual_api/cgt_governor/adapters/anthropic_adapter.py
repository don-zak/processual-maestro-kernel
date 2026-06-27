"""Anthropic Claude Adapter"""

from __future__ import annotations

import os

from .base import BaseLLMAdapter


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude API."""

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    @property
    def default_model(self) -> str:
        return os.environ.get("ANTHROPIC_DEFAULT_MODEL", "claude-3-5-haiku-latest")

    def is_configured(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY", ""))

    async def is_available(self) -> bool:
        if not self.is_configured():
            return False
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            await client.ping()
            return True
        except Exception:
            return False

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Anthropic adapter is not configured: ANTHROPIC_API_KEY is not set")

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=api_key)

        model = kwargs.get("model") or self.default_model
        response = await client.messages.create(
            model=model,
            system=system_prompt or "",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=kwargs.get("max_tokens", 2048),
            temperature=kwargs.get("temperature", 0.7),
        )
        return response.content[0].text if response.content else ""
