"""Central provider metadata for adapter configuration.

This module keeps provider environment bindings in one place so routers
do not need to duplicate hardcoded provider lists.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderEnvironment:
    provider_id: str
    display_name: str
    api_key_env: str
    model_env: str
    url_env: str = ""
    default_base_url: str = ""
    kind: str = "cloud_llm"
    auth_mode: str = "api_key"
    openai_compatible: bool = False


PROVIDER_ENVIRONMENTS: dict[str, ProviderEnvironment] = {
    "openai": ProviderEnvironment(
        provider_id="openai",
        display_name="OpenAI",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_DEFAULT_MODEL",
        openai_compatible=True,
    ),
    "anthropic": ProviderEnvironment(
        provider_id="anthropic",
        display_name="Anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_DEFAULT_MODEL",
    ),
    "gemini": ProviderEnvironment(
        provider_id="gemini",
        display_name="Gemini",
        api_key_env="GEMINI_API_KEY",
        model_env="GEMINI_DEFAULT_MODEL",
    ),
    "deepseek": ProviderEnvironment(
        provider_id="deepseek",
        display_name="DeepSeek",
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_DEFAULT_MODEL",
        openai_compatible=True,
    ),
    "opencode": ProviderEnvironment(
        provider_id="opencode",
        display_name="OpenCode",
        api_key_env="OPENCODE_API_KEY",
        model_env="OPENCODE_DEFAULT_MODEL",
        url_env="OPENCODE_API_URL",
        default_base_url="http://localhost:11434/v1",
        kind="local_or_self_hosted",
        auth_mode="optional_api_key",
        openai_compatible=True,
    ),
    "openrouter": ProviderEnvironment(
        provider_id="openrouter",
        display_name="OpenRouter",
        api_key_env="OPENROUTER_API_KEY",
        model_env="OPENROUTER_DEFAULT_MODEL",
        url_env="OPENROUTER_API_URL",
        default_base_url="https://openrouter.ai/api/v1",
        kind="router_gateway",
        openai_compatible=True,
    ),
    "generic_openai_compatible": ProviderEnvironment(
        provider_id="generic_openai_compatible",
        display_name="Generic OpenAI Compatible",
        api_key_env="GENERIC_OPENAI_API_KEY",
        model_env="GENERIC_OPENAI_DEFAULT_MODEL",
        url_env="GENERIC_OPENAI_API_URL",
        kind="customer_endpoint",
        auth_mode="optional_api_key",
        openai_compatible=True,
    ),
}


def normalize_provider_id(provider: str) -> str:
    return provider.lower().replace(" ", "_")


def provider_ids() -> set[str]:
    return set(PROVIDER_ENVIRONMENTS.keys())


def get_provider_environment(provider: str) -> ProviderEnvironment | None:
    return PROVIDER_ENVIRONMENTS.get(normalize_provider_id(provider))


def provider_env_map() -> dict[str, tuple[str, str, str]]:
    return {
        provider_id: (env.api_key_env, env.model_env, env.url_env)
        for provider_id, env in PROVIDER_ENVIRONMENTS.items()
    }


def provider_public_metadata(provider: str) -> dict[str, object]:
    env = get_provider_environment(provider)
    if not env:
        provider_id = normalize_provider_id(provider)
        return {
            "provider_id": provider_id,
            "display_name": provider,
            "kind": "unknown",
            "auth_mode": "unknown",
            "openai_compatible": False,
            "base_url_configurable": False,
            "default_base_url": "",
            "api_key_env": "",
            "model_env": "",
            "url_env": "",
        }
    return {
        "provider_id": env.provider_id,
        "display_name": env.display_name,
        "kind": env.kind,
        "auth_mode": env.auth_mode,
        "openai_compatible": env.openai_compatible,
        "base_url_configurable": bool(env.url_env),
        "default_base_url": env.default_base_url,
        "api_key_env": env.api_key_env,
        "model_env": env.model_env,
        "url_env": env.url_env,
    }
