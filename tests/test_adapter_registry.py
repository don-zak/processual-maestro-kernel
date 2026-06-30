from processual_api.cgt_governor.adapters.registry import LLMAdapterRegistry


def test_registry_discovers_openrouter_and_generic_adapter_once():
    registry = LLMAdapterRegistry()
    registry.discover()

    providers = registry.all()

    assert "openrouter" in providers
    assert "generic_openai_compatible" in providers
    assert list(providers.keys()).count("openrouter") == 1
    assert list(providers.keys()).count("generic_openai_compatible") == 1


def test_registry_provider_summary_keeps_existing_contract():
    registry = LLMAdapterRegistry()
    registry.discover()

    summary = registry.list_providers()
    names = {item["name"] for item in summary}

    assert "OpenRouter" in names
    assert "Generic OpenAI Compatible" in names
    assert all("configured" in item for item in summary)
    assert all("default_model" in item for item in summary)
