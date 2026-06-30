from processual_api.cgt_governor.adapters.provider_metadata import (
    get_provider_environment,
    provider_env_map,
    provider_ids,
    provider_public_metadata,
)


def test_provider_ids_include_expected_adapters():
    expected = {
        "openai",
        "anthropic",
        "gemini",
        "deepseek",
        "opencode",
        "openrouter",
        "generic_openai_compatible",
    }

    assert expected.issubset(provider_ids())


def test_provider_env_map_contains_expected_bindings():
    env_map = provider_env_map()

    assert env_map["openrouter"] == (
        "OPENROUTER_API_KEY",
        "OPENROUTER_DEFAULT_MODEL",
        "OPENROUTER_API_URL",
    )
    assert env_map["generic_openai_compatible"] == (
        "GENERIC_OPENAI_API_KEY",
        "GENERIC_OPENAI_DEFAULT_MODEL",
        "GENERIC_OPENAI_API_URL",
    )


def test_public_metadata_classifies_openai_compatible_providers():
    generic = provider_public_metadata("generic_openai_compatible")
    openrouter = provider_public_metadata("openrouter")
    opencode = provider_public_metadata("opencode")

    assert generic["kind"] == "customer_endpoint"
    assert generic["auth_mode"] == "optional_api_key"
    assert generic["openai_compatible"] is True
    assert generic["base_url_configurable"] is True

    assert openrouter["kind"] == "router_gateway"
    assert openrouter["openai_compatible"] is True
    assert openrouter["base_url_configurable"] is True

    assert opencode["kind"] == "local_or_self_hosted"
    assert opencode["auth_mode"] == "optional_api_key"


def test_provider_lookup_normalizes_names():
    env = get_provider_environment("Generic OpenAI Compatible")

    assert env is not None
    assert env.provider_id == "generic_openai_compatible"
