"""LLM Adapter Registry â€” discovers and manages all configured providers.

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

from .base import BaseLLMAdapter

logger = logging.getLogger("maestro.adapters")


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
        """Register an adapter instance."""
        name = adapter.provider_name.lower().replace(" ", "_")
        self._adapters[name] = adapter
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
