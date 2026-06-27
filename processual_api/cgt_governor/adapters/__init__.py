"""LLM Adapters for CGT Governor

Each adapter wraps a specific LLM provider behind a common interface.
Add new providers by subclassing BaseLLMAdapter and registering in the registry.
"""

from .anthropic_adapter import AnthropicAdapter
from .deepseek_adapter import DeepSeekAdapter
from .gemini_adapter import GeminiAdapter
from .openai_adapter import OpenAIAdapter
from .opencode_adapter import OpenCodeAdapter
from .registry import adapter_registry

__all__ = [
    "AnthropicAdapter",
    "DeepSeekAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    "OpenCodeAdapter",
    "adapter_registry",
]
