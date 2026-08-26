"""Anthropic Claude Adapter"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .base import BaseLLMAdapter

if TYPE_CHECKING:
    from anthropic.types import MessageParam


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
            models_api = getattr(client, "models", None)
            if models_api is not None:
                await models_api.list(limit=1)
                return True
            ping = getattr(client, "ping", None)
            if ping is None:
                return False
            await ping()
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
        model = str(kwargs.get("model") or self.default_model)
        max_tokens = int(kwargs.get("max_tokens", 2048))
        messages: list[MessageParam] = [{"role": "user", "content": prompt}]
        response = await client.messages.create(
            model=model,
            system=system_prompt or "",
            messages=messages,
            max_tokens=max_tokens,
        )
        if not response.content:
            return ""
        text = getattr(response.content[0], "text", None)
        return text if isinstance(text, str) else ""
