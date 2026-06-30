import asyncio

import pytest
from fastapi import HTTPException

from processual_api.routers import cgt_governor


def test_configure_adapter_applies_generic_openai_compatible_environment(monkeypatch):
    env_map = cgt_governor.provider_env_map()
    api_key_env, model_env, url_env = env_map["generic_openai_compatible"]

    for env_name in [api_key_env, model_env, url_env]:
        if env_name:
            monkeypatch.delenv(env_name, raising=False)

    captured = {}

    def fake_save_adapter_config(provider: str, api_key: str, model: str, base_url: str):
        captured["provider"] = provider
        captured["api_key"] = api_key
        captured["model"] = model
        captured["base_url"] = base_url

    monkeypatch.setattr(cgt_governor, "_save_adapter_config", fake_save_adapter_config)

    response = asyncio.run(
        cgt_governor.configure_adapter(
            cgt_governor.ConfigureAdapterRequest(
                provider="generic_openai_compatible",
                api_key="test-generic-key",
                model="llama3",
                base_url="http://localhost:11434/v1",
            ),
            _current_user={"sub": "admin_user"},
        )
    )

    assert response == {"provider": "generic_openai_compatible", "configured": True}

    assert captured == {
        "provider": "generic_openai_compatible",
        "api_key": "test-generic-key",
        "model": "llama3",
        "base_url": "http://localhost:11434/v1",
    }

    assert cgt_governor.os.environ[api_key_env] == "test-generic-key"
    assert cgt_governor.os.environ[model_env] == "llama3"
    assert cgt_governor.os.environ[url_env] == "http://localhost:11434/v1"


def test_configure_adapter_rejects_unknown_provider_without_saving(monkeypatch):
    saved = {"called": False}

    def fake_save_adapter_config(provider: str, api_key: str, model: str, base_url: str):
        saved["called"] = True

    monkeypatch.setattr(cgt_governor, "_save_adapter_config", fake_save_adapter_config)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            cgt_governor.configure_adapter(
                cgt_governor.ConfigureAdapterRequest(
                    provider="unknown_provider",
                    api_key="unused",
                    model="unused",
                    base_url="",
                ),
                _current_user={"sub": "admin_user"},
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Unknown provider: unknown_provider"
    assert saved["called"] is False


def test_adapters_status_returns_provider_metadata(monkeypatch):
    class DummyAdapter:
        provider_name = "Generic OpenAI Compatible"
        default_model = "llama3"

        def is_configured(self):
            return True

    class DummyRegistry:
        def all(self):
            return {"generic_openai_compatible": DummyAdapter()}

        def default(self):
            return DummyAdapter()

    def fake_provider_public_metadata(provider_id: str):
        assert provider_id == "generic_openai_compatible"
        return {
            "provider_id": provider_id,
            "display_name": "Generic OpenAI Compatible",
            "kind": "customer_endpoint",
            "auth_mode": "optional_api_key",
            "openai_compatible": True,
            "base_url_configurable": True,
            "default_base_url": "",
            "api_key_env": "GENERIC_OPENAI_API_KEY",
            "model_env": "GENERIC_OPENAI_DEFAULT_MODEL",
            "url_env": "GENERIC_OPENAI_API_URL",
        }

    monkeypatch.setattr(cgt_governor, "adapter_registry", DummyRegistry())
    monkeypatch.setattr(cgt_governor, "provider_public_metadata", fake_provider_public_metadata)

    response = asyncio.run(cgt_governor.adapters_status(current_user={"sub": "reader_user"}))

    assert response["default"] == "Generic OpenAI Compatible"
    assert len(response["providers"]) == 1

    provider = response["providers"][0]

    assert provider["provider_id"] == "generic_openai_compatible"
    assert provider["display_name"] == "Generic OpenAI Compatible"
    assert provider["kind"] == "customer_endpoint"
    assert provider["auth_mode"] == "optional_api_key"
    assert provider["openai_compatible"] is True
    assert provider["base_url_configurable"] is True
    assert provider["api_key_env"] == "GENERIC_OPENAI_API_KEY"
    assert provider["model_env"] == "GENERIC_OPENAI_DEFAULT_MODEL"
    assert provider["url_env"] == "GENERIC_OPENAI_API_URL"
    assert provider["name"] == "Generic OpenAI Compatible"
    assert provider["configured"] is True
    assert provider["default_model"] == "llama3"