from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import processual_api.services.enterprise_r10_binding_creation_18 as creation
from processual_api.services.enterprise_qualification_18 import (
    get_task_execution_policy,
)

CASE_ID = "institution_case_binding_18"
CLIENT_ID = "client_binding_18"
TASK_ID = "sandbox_capability_probe"


def _institution_case() -> dict:
    return {
        "case_id": CASE_ID,
        "client_id": CLIENT_ID,
        "integration_track": "camara",
        "status": "qualification_activated",
        "phase": "qualification_activated",
        "tasks": [
            {
                "task_id": TASK_ID,
                "validation": "passed",
            }
        ],
    }


def _qualification_store() -> dict:
    policy = get_task_execution_policy(
        "camara",
        TASK_ID,
    )
    now = datetime.now(UTC)

    return {
        "version": 1,
        "grants": [
            {
                "grant_id": "qgrant_binding_18",
                "case_id": CASE_ID,
                "client_id": CLIENT_ID,
                "integration_track": "camara",
                "approved_task_ids": [TASK_ID],
                "approved_profile_ids": [
                    policy.credential_profile_id
                ],
                "issued_by_supervisor_id": "supervisor",
                "supervisor_session_key_id": (
                    "supsk_identifier_only"
                ),
                "issued_at": now.isoformat(),
                "expires_at": (
                    now + timedelta(days=7)
                ).isoformat(),
                "status": "activated",
                "environment": "sandbox",
                "revision": 1,
                "constraints": [
                    "sandbox_only",
                    "read_only",
                ],
                "production_allowed": False,
                "runtime_connector_approved": False,
                "write_allowed": False,
                "restricted_allowed": False,
                "external_http_allowed": False,
                "raw_secret_visible": False,
            }
        ],
        "decisions": [],
        "audit": [],
    }


def _write_json(path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _external_case() -> SimpleNamespace:
    policy = get_task_execution_policy(
        "camara",
        TASK_ID,
    )

    return SimpleNamespace(
        case_id="external_case_binding_18",
        client_id=CLIENT_ID,
        connector_id=policy.connector_id,
        credential_profile_id=(
            policy.credential_profile_id
        ),
        target_environment="sandbox",
        state="readiness_approved",
    )


def test_create_binding_uses_authoritative_resources(
    tmp_path,
    monkeypatch,
) -> None:
    qualification_path = (
        tmp_path / "qualification.json"
    )
    binding_path = tmp_path / "bindings.json"

    _write_json(
        qualification_path,
        _qualification_store(),
    )

    monkeypatch.setattr(
        creation,
        "get_external_connectivity_case",
        lambda case_id, path=None: _external_case(),
    )

    result = creation.create_enterprise_r10_binding(
        institution_case=_institution_case(),
        institution_task_id=TASK_ID,
        client_id=CLIENT_ID,
        external_connectivity_case_id=(
            "external_case_binding_18"
        ),
        actor=CLIENT_ID,
        qualification_store_path=qualification_path,
        binding_store_path=binding_path,
    )

    assert result["status"] == "validated"
    assert result["credential_issued"] is False
    assert result["qualification_key_issued"] is False
    assert result["sandbox_api_key_issued"] is False
    assert result["connector_executed"] is False
    assert result["external_http_allowed"] is False
    assert result["production_allowed"] is False

    binding = result["binding"]
    assert binding["institution_case_id"] == CASE_ID
    assert binding["institution_task_id"] == TASK_ID
    assert binding["client_id"] == CLIENT_ID
    assert binding["status"] == "validated"
    assert binding["next_required_state"] == (
        "qualification_key"
    )

    saved = json.loads(
        binding_path.read_text(encoding="utf-8")
    )

    assert len(saved["bindings"]) == 1
    assert saved["audit"][0]["event"] == (
        "enterprise_r10_binding_created"
    )

    forbidden_exact_keys = {
        "api_key",
        "sandbox_api_key",
        "qualification_key",
        "raw_key",
        "raw_value",
        "key_hash",
        "hashed_key",
        "authorization",
        "access_token",
        "refresh_token",
        "client_secret",
        "provider_secret",
        "supervisor_session_key",
    }

    def assert_secret_free(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                assert (
                    str(key).strip().lower()
                    not in forbidden_exact_keys
                )
                assert_secret_free(child)
            return

        if isinstance(value, list):
            for child in value:
                assert_secret_free(child)

    assert_secret_free(saved)

    assert (
        saved["bindings"][0][
            "external_qualification_key_id"
        ]
        is None
    )
    assert (
        saved["bindings"][0][
            "external_sandbox_api_key_id"
        ]
        is None
    )


def test_create_binding_requires_activated_grant(
    tmp_path,
    monkeypatch,
) -> None:
    store = _qualification_store()
    store["grants"][0]["status"] = "approved"

    qualification_path = (
        tmp_path / "qualification.json"
    )
    _write_json(qualification_path, store)

    monkeypatch.setattr(
        creation,
        "get_external_connectivity_case",
        lambda case_id, path=None: _external_case(),
    )

    with pytest.raises(
        creation.EnterpriseR10BindingCreationError,
        match="activated_qualification_grant_not_found",
    ):
        creation.create_enterprise_r10_binding(
            institution_case=_institution_case(),
            institution_task_id=TASK_ID,
            client_id=CLIENT_ID,
            external_connectivity_case_id=(
                "external_case_binding_18"
            ),
            actor=CLIENT_ID,
            qualification_store_path=qualification_path,
            binding_store_path=(
                tmp_path / "bindings.json"
            ),
        )


def test_create_binding_rejects_cross_client(
    tmp_path,
) -> None:
    qualification_path = (
        tmp_path / "qualification.json"
    )
    _write_json(
        qualification_path,
        _qualification_store(),
    )

    with pytest.raises(
        creation.EnterpriseR10BindingCreationError,
        match="institution_case_client_mismatch",
    ):
        creation.create_enterprise_r10_binding(
            institution_case=_institution_case(),
            institution_task_id=TASK_ID,
            client_id="different-client",
            external_connectivity_case_id=(
                "external_case_binding_18"
            ),
            actor="different-client",
            qualification_store_path=qualification_path,
            binding_store_path=(
                tmp_path / "bindings.json"
            ),
        )


def test_create_binding_rejects_duplicate(
    tmp_path,
    monkeypatch,
) -> None:
    qualification_path = (
        tmp_path / "qualification.json"
    )
    binding_path = tmp_path / "bindings.json"

    _write_json(
        qualification_path,
        _qualification_store(),
    )

    monkeypatch.setattr(
        creation,
        "get_external_connectivity_case",
        lambda case_id, path=None: _external_case(),
    )

    arguments = {
        "institution_case": _institution_case(),
        "institution_task_id": TASK_ID,
        "client_id": CLIENT_ID,
        "external_connectivity_case_id": (
            "external_case_binding_18"
        ),
        "actor": CLIENT_ID,
        "qualification_store_path": qualification_path,
        "binding_store_path": binding_path,
    }

    creation.create_enterprise_r10_binding(
        **arguments
    )

    with pytest.raises(
        creation.EnterpriseR10BindingCreationError,
        match="active_task_binding_already_exists",
    ):
        creation.create_enterprise_r10_binding(
            **arguments
        )
