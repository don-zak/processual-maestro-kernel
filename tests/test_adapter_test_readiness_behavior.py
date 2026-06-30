import asyncio

import pytest
from fastapi import HTTPException

from processual_api.routers import cgt_governor


class DummyAdapter:
    def __init__(
        self,
        provider_name: str,
        default_model: str,
        configured: bool,
        available=True,
    ):
        self.provider_name = provider_name
        self.default_model = default_model
        self._configured = configured
        self._available = available

    def is_configured(self):
        return self._configured

    async def is_available(self):
        if isinstance(self._available, Exception):
            raise self._available
        return self._available


class DummyRegistry:
    def __init__(self, adapters: dict[str, DummyAdapter], default_key: str | None = None):
        self.adapters = adapters
        self.default_key = default_key

    def get(self, provider: str):
        return self.adapters.get(provider)

    def all(self):
        return self.adapters

    def default(self):
        if self.default_key is None:
            return None
        return self.adapters[self.default_key]


def _metadata(provider_id: str) -> dict:
    return {
        "provider_id": provider_id,
        "display_name": provider_id.replace("_", " ").title(),
        "kind": "customer_endpoint",
        "auth_mode": "optional_api_key",
        "openai_compatible": True,
        "base_url_configurable": True,
        "default_base_url": "",
        "api_key_env": f"{provider_id.upper()}_API_KEY",
        "model_env": f"{provider_id.upper()}_DEFAULT_MODEL",
        "url_env": f"{provider_id.upper()}_API_URL",
    }


def test_adapter_test_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(cgt_governor, "adapter_registry", DummyRegistry({}))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            cgt_governor.test_adapter(
                cgt_governor.TestAdapterRequest(provider="missing_provider"),
                _current_user={"sub": "admin_user"},
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Adapter not found: missing_provider"


def test_adapter_test_returns_metadata_on_success(monkeypatch):
    monkeypatch.setattr(
        cgt_governor,
        "adapter_registry",
        DummyRegistry(
            {
                "generic_openai_compatible": DummyAdapter(
                    provider_name="Generic OpenAI Compatible",
                    default_model="llama3",
                    configured=True,
                    available=True,
                )
            }
        ),
    )
    monkeypatch.setattr(cgt_governor, "provider_public_metadata", _metadata)

    response = asyncio.run(
        cgt_governor.test_adapter(
            cgt_governor.TestAdapterRequest(provider="generic_openai_compatible"),
            _current_user={"sub": "admin_user"},
        )
    )

    assert response["provider"] == "generic_openai_compatible"
    assert response["provider_id"] == "generic_openai_compatible"
    assert response["name"] == "Generic OpenAI Compatible"
    assert response["kind"] == "customer_endpoint"
    assert response["auth_mode"] == "optional_api_key"
    assert response["openai_compatible"] is True
    assert response["base_url_configurable"] is True
    assert response["ok"] is True
    assert isinstance(response["latency_ms"], int)
    assert response["model"] == "llama3"
    assert response["message"] == "Connected"


def test_adapter_test_returns_error_payload_on_adapter_exception(monkeypatch):
    monkeypatch.setattr(
        cgt_governor,
        "adapter_registry",
        DummyRegistry(
            {
                "generic_openai_compatible": DummyAdapter(
                    provider_name="Generic OpenAI Compatible",
                    default_model="llama3",
                    configured=True,
                    available=RuntimeError("boom"),
                )
            }
        ),
    )
    monkeypatch.setattr(cgt_governor, "provider_public_metadata", _metadata)

    response = asyncio.run(
        cgt_governor.test_adapter(
            cgt_governor.TestAdapterRequest(provider="generic_openai_compatible"),
            _current_user={"sub": "admin_user"},
        )
    )

    assert response["provider"] == "generic_openai_compatible"
    assert response["provider_id"] == "generic_openai_compatible"
    assert response["ok"] is False
    assert isinstance(response["latency_ms"], int)
    assert response["model"] == "llama3"
    assert response["message"] == "Adapter error: RuntimeError"


def test_adapters_readiness_summarizes_all_adapter_results(monkeypatch):
    adapters = {
        "ok_provider": DummyAdapter(
            provider_name="OK Provider",
            default_model="ok-model",
            configured=True,
            available=True,
        ),
        "down_provider": DummyAdapter(
            provider_name="Down Provider",
            default_model="down-model",
            configured=False,
            available=False,
        ),
        "error_provider": DummyAdapter(
            provider_name="Error Provider",
            default_model="error-model",
            configured=True,
            available=RuntimeError("boom"),
        ),
    }

    monkeypatch.setattr(
        cgt_governor,
        "adapter_registry",
        DummyRegistry(adapters, default_key="ok_provider"),
    )
    monkeypatch.setattr(cgt_governor, "provider_public_metadata", _metadata)

    response = asyncio.run(
        cgt_governor.adapters_readiness(_current_user={"sub": "admin_user"})
    )

    assert response["total"] == 3
    assert response["configured_count"] == 2
    assert response["ok_count"] == 1
    assert response["default"] == "OK Provider"

    by_provider = {item["provider"]: item for item in response["providers"]}

    assert by_provider["ok_provider"]["ok"] is True
    assert by_provider["ok_provider"]["message"] == "Connected"
    assert by_provider["ok_provider"]["model"] == "ok-model"
    assert by_provider["ok_provider"]["provider_id"] == "ok_provider"

    assert by_provider["down_provider"]["ok"] is False
    assert by_provider["down_provider"]["message"] == "Unreachable"
    assert by_provider["down_provider"]["configured"] is False

    assert by_provider["error_provider"]["ok"] is False
    assert by_provider["error_provider"]["message"] == "Adapter error: RuntimeError"
    assert by_provider["error_provider"]["configured"] is True

    for provider in response["providers"]:
        assert isinstance(provider["latency_ms"], int)
        assert "kind" in provider
        assert "auth_mode" in provider
        assert "openai_compatible" in provider
        assert "base_url_configurable" in provider