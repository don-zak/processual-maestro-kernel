import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.routers import settings as settings_router

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_ROUTER = ROOT / "processual_api" / "routers" / "settings.py"


def _settings_source() -> str:
    return SETTINGS_ROUTER.read_text(encoding="utf-8")


def test_api_key_create_request_declares_profile_payload_fields():
    source = _settings_source()

    required_fields = [
        "category: str | None",
        "role: str | None",
        "scopes: list[str] | None",
        "quota_limit_override: int | None",
        "expires_at: str | None",
        "purpose: str | None",
        "issued_to: str | None",
    ]

    for field in required_fields:
        assert field in source


def test_api_key_profile_defaults_include_all_admin_provisioning_categories():
    source = _settings_source()

    required_categories = [
        "client_api",
        "pilot_client",
        "external_partner",
        "service_integration",
        "billing_service",
        "support_viewer",
        "ops_admin",
        "billing_admin",
        "security_admin",
        "owner_admin",
        "emergency_bootstrap",
    ]

    assert "API_KEY_PROFILE_DEFAULTS" in source
    for category in required_categories:
        assert category in source


def test_create_api_key_accepts_and_persists_profile_payload(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    body = settings_router.ApiKeyCreateRequest(
        category="external_partner",
        role="partner",
        scopes=["read:health", "read:adapters"],
        plan_id="Starter",
        quota_limit_override=25,
        expires_at="2026-12-31T00:00:00+00:00",
        client_id="partner-client",
        user_id="partner-user",
        label="Partner access key",
        purpose="External partner evaluation",
        issued_to="ACME Partner",
    )

    result = asyncio.run(
        settings_router.create_api_key(
            body=body,
            current_user={
                "sub": "owner-admin",
                "client_id": "owner-client",
                "role": "security_admin",
            },
        )
    )

    assert result["api_key"]
    assert result["category"] == "external_partner"
    assert result["role"] == "partner"
    assert result["scopes"] == ["read:health", "read:adapters"]
    assert result["quota_limit_override"] == 25
    assert result["quota_limit"] == 25
    assert result["expires_at"] == "2026-12-31T00:00:00+00:00"
    assert result["client_id"] == "partner-client"
    assert result["user_id"] == "partner-user"
    assert result["label"] == "Partner access key"
    assert result["purpose"] == "External partner evaluation"
    assert result["issued_to"] == "ACME Partner"
    assert result["created_by_admin_role"] == "security_admin"

    raw = settings_router._load_raw("owner-admin")
    stored = raw["api_keys"][0]

    assert stored["category"] == "external_partner"
    assert stored["role"] == "partner"
    assert stored["scopes"] == ["read:health", "read:adapters"]
    assert stored["quota_limit_override"] == 25
    assert stored["quota_limit"] == 25
    assert stored["expires_at"] == "2026-12-31T00:00:00+00:00"
    assert stored["purpose"] == "External partner evaluation"
    assert stored["issued_to"] == "ACME Partner"
    assert stored["created_by_admin_role"] == "security_admin"
    assert "hashed" in stored
    assert "api_key" not in stored


def test_list_api_keys_returns_profile_metadata_without_raw_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    body = settings_router.ApiKeyCreateRequest(
        category="service_integration",
        role="service",
        scopes=["read:health"],
        label="Service integration key",
        purpose="Internal service sync",
        issued_to="maestro-worker",
    )

    asyncio.run(
        settings_router.create_api_key(
            body=body,
            current_user={
                "sub": "owner-admin",
                "client_id": "owner-client",
                "role": "ops_admin",
            },
        )
    )

    keys = asyncio.run(
        settings_router.list_api_keys(
            current_user={
                "sub": "owner-admin",
                "role": "ops_admin",
            }
        )
    )

    assert len(keys) == 1
    listed = keys[0]

    assert listed["category"] == "service_integration"
    assert listed["role"] == "service"
    assert listed["scopes"] == ["read:health"]
    assert listed["label"] == "Service integration key"
    assert listed["purpose"] == "Internal service sync"
    assert listed["issued_to"] == "maestro-worker"
    assert listed["created_by_admin_role"] == "ops_admin"
    assert "api_key" not in listed
    assert "hashed" not in listed


def test_create_api_key_rejects_unknown_profile_category(monkeypatch, tmp_path):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    body = settings_router.ApiKeyCreateRequest(
        category="unknown_root_shell",
        label="Invalid key",
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_router.create_api_key(
                body=body,
                current_user={
                    "sub": "owner-admin",
                    "role": "security_admin",
                },
            )
        )

    assert exc.value.status_code == 400
    assert "Unknown API key category" in exc.value.detail


def test_default_create_api_key_keeps_backward_compatible_client_profile(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(settings_router, "_DATA_DIR", tmp_path)

    result = asyncio.run(
        settings_router.create_api_key(
            body=settings_router.ApiKeyCreateRequest(label="Default key"),
            current_user={
                "sub": "owner-admin",
                "client_id": "owner-client",
                "role": "security_admin",
            },
        )
    )

    assert result["category"] == "client_api"
    assert result["role"] == "client"
    assert result["profile"] == "client"
    assert result["scopes"] == settings_router.DEFAULT_API_KEY_SCOPES

def test_service_integration_profile_defaults_support_runtime_integration():
    from processual_api.routers import settings as settings_router

    defaults = settings_router.API_KEY_PROFILE_DEFAULTS["service_integration"]

    assert defaults["role"] == "service"
    assert "read:health" in defaults["scopes"]
    assert "read:adapters" in defaults["scopes"]
    assert "read:governor" in defaults["scopes"]
    assert "run:govern" in defaults["scopes"]
