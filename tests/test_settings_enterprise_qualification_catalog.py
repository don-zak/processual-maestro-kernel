from __future__ import annotations

from processual_api.routers import settings as settings_router
from processual_api.routers.settings_enterprise_integration_runtime import (
    enterprise_integration_console_payload,
)


def _client(plan_id: str = "enterprise_core") -> dict:
    return {
        "sub": "qualification-client",
        "user_id": "qualification-client",
        "client_id": "qualification-client",
        "role": "client",
        "plan_id": plan_id,
    }


def test_eligible_enterprise_get_exposes_safe_server_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "enterprise_core"},
            "api_keys": [],
        },
    )

    payload = enterprise_integration_console_payload(current_user=_client())
    catalog = payload["qualification_catalog"]

    assert catalog["enabled"] is True
    assert catalog["source"] == "catalog"
    assert catalog["profiles"]
    assert catalog["scopes"]

    profile = catalog["profiles"][0]
    assert profile["credential_profile_id"]
    assert profile["required_input_ids"]
    assert profile["required_security_control_ids"]
    assert profile["sandbox_required"] is True
    assert profile["production_credential_approval_required"] is True
    assert profile["runtime_connector_approved"] is False

    scope = catalog["scopes"][0]
    assert scope["scope_id"]
    assert scope["access_level"] in {"read", "write", "restricted"}
    assert scope["production_allowed_without_approval"] is False

    text = repr(catalog).lower()
    assert "raw api key values" not in text
    assert "raw oauth client secrets" not in text
    assert "private key material" not in text


def test_locked_plan_get_does_not_expose_qualification_catalog(monkeypatch) -> None:
    monkeypatch.setattr(
        settings_router,
        "_load_raw",
        lambda user_id: {
            "subscription": {"plan_id": "starter"},
            "api_keys": [],
        },
    )

    payload = enterprise_integration_console_payload(current_user=_client("starter"))

    assert payload["qualification_catalog"] == {
        "enabled": False,
        "source": "catalog",
        "profiles": [],
        "scopes": [],
    }
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
