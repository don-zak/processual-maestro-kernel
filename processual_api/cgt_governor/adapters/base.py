"""Base LLM Adapter — abstract interface for all LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMAdapter(ABC):
    """Common interface for all LLM providers.

    Each adapter implements:
    - generate(): send a prompt and return the response text
    - is_configured(): whether credentials are provided
    - is_available(): whether the provider endpoint is reachable

    Properties:
    - provider_name: human-readable provider name (e.g. "OpenAI")
    - default_model: the default model identifier for this provider
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs,
    ) -> str:
        """Send a prompt to the LLM and return the generated text."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if the provider has valid credentials configured."""

    async def is_available(self) -> bool:
        """Check if the provider endpoint is reachable.

        Default implementation calls generate with a simple ping.
        Override for more efficient health checks.
        """
        return self.is_configured()

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name, e.g. 'OpenAI'."""

    @property
    def default_model(self) -> str:
        """Default model identifier for this provider."""
        return ""
