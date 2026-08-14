import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.routers.settings_admin_api_key_provisioning import (
    _require_api_key_provisioning_admin,
    admin_api_key_operational_profiles,
)

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
WORKSPACE_SCRIPT = JS / "admin_api_key_provisioning_workspace.js"
SESSION_SCRIPT = JS / "admin_session.js"
ROUTERS_INIT = ROOT / "processual_api" / "routers" / "__init__.py"


def _workspace_source() -> str:
    return WORKSPACE_SCRIPT.read_text(encoding="utf-8")


def _session_source() -> str:
    return SESSION_SCRIPT.read_text(encoding="utf-8")


def test_admin_operational_profile_catalog_requires_admin_authority() -> None:
    _require_api_key_provisioning_admin({"role": "security_admin", "scopes": []})
    _require_api_key_provisioning_admin({"role": "client", "scopes": ["admin:api_keys:read"]})

    with pytest.raises(HTTPException) as exc_info:
        _require_api_key_provisioning_admin({"role": "client", "scopes": ["read:health"]})

    assert exc_info.value.status_code == 403


def test_admin_operational_profile_catalog_is_safe_and_non_production() -> None:
    payload = asyncio.run(
        admin_api_key_operational_profiles(
            {"role": "security_admin", "scopes": ["admin:api_keys:write"]}
        )
    )

    assert payload["admin_provisioning_catalog"] is True
    assert payload["selection_authority"] == "api_key_operational_profiles"
    assert payload["raw_secret_visible"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False
    assert payload["profiles"]
    assert payload["profile_count"] == len(payload["profiles"])

    for profile in payload["profiles"]:
        assert profile["client_visible"] is True
        assert profile["production_allowed"] is False
        assert profile["runtime_connector_approved"] is False
        assert "allowed_scopes" in profile
        assert "forbidden_scopes" in profile


def test_provisioning_workspace_exposes_mode_profile_and_access_preview() -> None:
    source = _workspace_source()

    required = [
        "Provisioning Workspace",
        "admin-api-key-provisioning-mode",
        "Standard / Integration Key",
        "External Evaluation",
        "admin-api-key-operational-profile",
        "/settings/admin/api-key-operational-profiles",
        "Selected operational intent only.",
        "Access Preview",
        "Key scopes currently configured",
        "Selected operational intent",
        "production",
        "runtime_connector",
    ]
    for marker in required:
        assert marker in source


def test_operational_profile_catalog_is_preview_only_and_does_not_mutate_key_scopes() -> None:
    source = _workspace_source()

    assert "This catalog does not grant runtime authority by itself" in source
    assert "does not mutate the key scopes below" in source
    assert "applySelectedProfileScopes" not in source
    assert "admin-api-key-apply-profile-scopes" not in source
    assert "target.value = allowed.join" not in source


def test_external_evaluation_mode_cannot_use_standard_key_generation() -> None:
    source = _workspace_source()

    assert "provisioningMode() === 'external_evaluation'" in source
    assert "button.disabled = true" in source
    assert "button.dataset.evaluationModeDisabled = 'true'" in source
    assert "evaluation grant authority cannot be bypassed" in source
    assert "/settings/admin/evaluation-grants" in source
    assert "This preview does not issue a key." in source
    assert "fetch('/settings/api-keys'" not in source
    assert "POST /settings/api-keys" not in source


def test_workspace_uses_backend_catalog_and_does_not_store_secrets() -> None:
    source = _workspace_source()

    assert "requestJson(PROFILE_ENDPOINT)" in source
    assert "payload.profiles" in source
    assert "profile.allowed_scopes" in source
    assert "profile.forbidden_scopes" in source
    assert "sessionStorage.setItem" not in source
    assert "localStorage.setItem" not in source
    assert "raw_secret" not in source.lower()


def test_workspace_initialization_is_bounded_and_does_not_observe_dom_forever() -> None:
    source = _workspace_source()

    assert "const MAX_INIT_ATTEMPTS = 20" in source
    assert "const INIT_RETRY_MS = 100" in source
    assert "initAttempts < MAX_INIT_ATTEMPTS" in source
    assert "window.setTimeout(initializeWorkspace, INIT_RETRY_MS)" in source
    assert "MutationObserver" not in source
    assert "while (" not in source


def test_workspace_updates_local_usage_examples_to_current_dev_port() -> None:
    source = _workspace_source()

    assert "127.0.0.1:8000" in source
    assert "127.0.0.1:18080" in source
    assert "replaceAll('127.0.0.1:8000', '127.0.0.1:18080')" in source


def test_workspace_script_loads_only_after_verified_admin_session() -> None:
    source = _session_source()

    required = [
        "API_KEY_WORKSPACE_SCRIPT_SELECTOR",
        "admin_api_key_provisioning_workspace.js?v=adminapikeyworkspace01",
        "function loadApiKeyProvisioningWorkspace()",
        "script.dataset.adminApiKeyProvisioningWorkspace = 'true'",
        "document.body.dataset.adminSession = 'ok'",
        "loadApiKeyProvisioningWorkspace();",
    ]
    for marker in required:
        assert marker in source

    assert source.index("document.body.dataset.adminSession = 'ok'") < source.index(
        "loadApiKeyProvisioningWorkspace();"
    )
    assert source.index("if (!isAdminSession(me))") < source.index(
        "loadApiKeyProvisioningWorkspace();"
    )


def test_admin_provisioning_route_extension_is_registered() -> None:
    source = ROUTERS_INIT.read_text(encoding="utf-8")

    assert "settings_admin_api_key_provisioning" in source
