"""LLM Adapter Registry — discovers and manages all configured providers.

Usage:
    from processual_api.cgt_governor.adapters.registry import adapter_registry
    adapter_registry.discover()
    adapter = adapter_registry.get("openai")
    if adapter and adapter.is_configured():
        text = await adapter.generate("Hello")
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .base import BaseLLMAdapter
from .execution_fanout import run_with_execution_fanout

logger = logging.getLogger("maestro.adapters")


class _GovernedLLMAdapter(BaseLLMAdapter):
    """Transparent adapter proxy that enforces cross-worker execution fan-out."""

    def __init__(self, adapter: BaseLLMAdapter) -> None:
        self._adapter = adapter

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        async def operation() -> str:
            return await self._adapter.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                **kwargs,
            )

        return await run_with_execution_fanout(self.provider_name, operation)

    def is_configured(self) -> bool:
        return self._adapter.is_configured()

    async def is_available(self) -> bool:
        return await self._adapter.is_available()

    @property
    def provider_name(self) -> str:
        return self._adapter.provider_name

    @property
    def default_model(self) -> str:
        return self._adapter.default_model

    def __getattr__(self, name: str) -> Any:
        return getattr(self._adapter, name)


class LLMAdapterRegistry:
    """Registry of all LLM adapters.

    Adapters register themselves, then the registry can:
    - list all available providers
    - get a specific adapter by name
    - get the default adapter
    - check which providers are configured
    """

    def __init__(self):
        self._adapters: dict[str, BaseLLMAdapter] = {}

    def register(self, adapter: BaseLLMAdapter) -> None:
        """Register an adapter instance behind the execution fan-out governor."""
        governed = adapter if isinstance(adapter, _GovernedLLMAdapter) else _GovernedLLMAdapter(adapter)
        name = governed.provider_name.lower().replace(" ", "_")
        self._adapters[name] = governed
        logger.debug("Adapter registered: %s", name)

    def get(self, name: str) -> BaseLLMAdapter | None:
        """Get an adapter by name (case-insensitive)."""
        key = name.lower().replace(" ", "_")
        return self._adapters.get(key)

    def all(self) -> dict[str, BaseLLMAdapter]:
        """Return all registered adapters."""
        return dict(self._adapters)

    def configured(self) -> dict[str, BaseLLMAdapter]:
        """Return only adapters with valid credentials."""
        return {k: v for k, v in self._adapters.items() if v.is_configured()}

    def default(self) -> BaseLLMAdapter | None:
        """Return the default adapter based on LLM_DEFAULT_PROVIDER env var."""
        default_name = os.environ.get("LLM_DEFAULT_PROVIDER", "")
        if default_name:
            return self.get(default_name) or next(iter(self.configured().values()), None)
        configured = self.configured()
        return next(iter(configured.values()), None) if configured else None

    def list_providers(self) -> list[dict]:
        """Return a summary of all providers for the API."""
        return [
            {
                "name": adapter.provider_name,
                "configured": adapter.is_configured(),
                "default_model": adapter.default_model,
            }
            for adapter in self._adapters.values()
        ]

    def discover(self) -> None:
        """Auto-discover and import all adapter modules.

        This is called automatically at startup from the plugin.
        """
        from .anthropic_adapter import AnthropicAdapter
        from .deepseek_adapter import DeepSeekAdapter
        from .gemini_adapter import GeminiAdapter
        from .openai_adapter import OpenAIAdapter
        from .openai_compatible_adapter import GenericOpenAICompatibleAdapter
        from .opencode_adapter import OpenCodeAdapter
        from .openrouter_adapter import OpenRouterAdapter

        for adapter_cls in [
            OpenAIAdapter,
            GenericOpenAICompatibleAdapter,
            AnthropicAdapter,
            GeminiAdapter,
            DeepSeekAdapter,
            OpenCodeAdapter,
            OpenRouterAdapter,
        ]:
            try:
                self.register(adapter_cls())  # type: ignore[abstract]
            except Exception as exc:
                logger.warning("Failed to register %s: %s", adapter_cls.__name__, exc)


adapter_registry = LLMAdapterRegistry()
