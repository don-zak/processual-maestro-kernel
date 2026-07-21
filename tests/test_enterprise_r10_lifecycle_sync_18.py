from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import processual_api.services.enterprise_r10_lifecycle_sync_18 as sync

BINDING_ID = "er10bind_sync_18"
CASE_ID = "institution_case_sync_18"
TASK_ID = "sandbox_capability_probe"
CLIENT_ID = "client_sync_18"
EXTERNAL_CASE_ID = "external_case_sync_18"


def _binding_store(path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bindings": [
                    {
                        "binding_id": BINDING_ID,
                        "revision": 1,
                        "previous_binding_id": None,
                        "institution_case_id": CASE_ID,
                        "institution_task_id": TASK_ID,
                        "qualification_grant_id": (
                            "qgrant_sync_18"
                        ),
                        "client_id": CLIENT_ID,
                        "integration_track": "camara",
                        "external_connectivity_case_id": (
                            EXTERNAL_CASE_ID
                        ),
                        "connector_id": "camara-quality-on-demand",
                        "operational_profile_id": (
                            "sandbox-read-only"
                        ),
                        "target_environment": "sandbox",
                        "requested_scope_ids": [
                            "quality-on-demand:read"
                        ],
                        "external_case_state": (
                            "readiness_approved"
                        ),
                        "next_required_state": (
                            "qualification_key"
                        ),
                        "external_qualification_key_id": None,
                        "external_sandbox_api_key_id": None,
                        "status": "validated",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                        "created_by": CLIENT_ID,
                        "production_allowed": False,
                        "runtime_connector_approved": False,
                        "external_http_allowed": False,
                        "write_allowed": False,
                        "restricted_allowed": False,
                        "raw_secret_visible": False,
                    }
                ],
                "audit": [],
            }
        ),
        encoding="utf-8",
    )


def _external_case(state: str) -> SimpleNamespace:
    return SimpleNamespace(
        case_id=EXTERNAL_CASE_ID,
        client_id=CLIENT_ID,
        integration_task_id=TASK_ID,
        connector_id="camara-quality-on-demand",
        credential_profile_id="camara-oauth2-client",
        target_environment="sandbox",
        state=state,
    )


def test_sync_qualification_key_issued(
    tmp_path,
    monkeypatch,
) -> None:
    binding_path = tmp_path / "bindings.json"
    _binding_store(binding_path)

    monkeypatch.setattr(
        sync,
        "get_external_connectivity_case",
        lambda case_id, path=None: _external_case(
            "qualification_key_issued"
        ),
    )

    monkeypatch.setattr(
        sync,
        "load_external_connectivity_case_store",
        lambda path=None: SimpleNamespace(
            qualification_keys=(
                SimpleNamespace(
                    case_id=EXTERNAL_CASE_ID,
                    qualification_key_id="ecqk_sync_18",
                    issued_at="2026-01-02T00:00:00+00:00",
                ),
            ),
            sandbox_api_keys=(),
        ),
    )

    result = sync.synchronize_enterprise_r10_binding(
        BINDING_ID,
        client_id=CLIENT_ID,
        institution_case_id=CASE_ID,
        institution_task_id=TASK_ID,
        actor=CLIENT_ID,
        binding_store_path=binding_path,
    )

    assert result["status"] == "synchronized"
    assert result["binding"]["status"] == (
        "qualification_key_issued"
    )
    assert result["binding"][
        "external_qualification_key_id"
    ] == "ecqk_sync_18"
    assert result["binding"][
        "external_sandbox_api_key_id"
    ] is None
    assert result["raw_qualification_key_returned"] is False
    assert result["raw_sandbox_api_key_returned"] is False
    assert result["connector_executed"] is False


def test_sync_sandbox_api_key_issued(
    tmp_path,
    monkeypatch,
) -> None:
    binding_path = tmp_path / "bindings.json"
    _binding_store(binding_path)

    monkeypatch.setattr(
        sync,
        "get_external_connectivity_case",
        lambda case_id, path=None: _external_case(
            "sandbox_api_key_issued"
        ),
    )

    monkeypatch.setattr(
        sync,
        "load_external_connectivity_case_store",
        lambda path=None: SimpleNamespace(
            qualification_keys=(
                SimpleNamespace(
                    case_id=EXTERNAL_CASE_ID,
                    qualification_key_id="ecqk_sync_18",
                    issued_at="2026-01-02T00:00:00+00:00",
                ),
            ),
            sandbox_api_keys=(
                SimpleNamespace(
                    case_id=EXTERNAL_CASE_ID,
                    sandbox_api_key_id="ecsbk_sync_18",
                    issued_at="2026-01-03T00:00:00+00:00",
                ),
            ),
        ),
    )

    result = sync.synchronize_enterprise_r10_binding(
        BINDING_ID,
        client_id=CLIENT_ID,
        institution_case_id=CASE_ID,
        institution_task_id=TASK_ID,
        actor=CLIENT_ID,
        binding_store_path=binding_path,
    )

    assert result["binding"]["status"] == (
        "sandbox_api_key_issued"
    )
    assert result["binding"][
        "external_sandbox_api_key_id"
    ] == "ecsbk_sync_18"
    assert result["next_required_state"] == (
        "controlled_sandbox_dispatcher"
    )


def test_sync_rejects_missing_qualification_reference(
    tmp_path,
    monkeypatch,
) -> None:
    binding_path = tmp_path / "bindings.json"
    _binding_store(binding_path)

    monkeypatch.setattr(
        sync,
        "get_external_connectivity_case",
        lambda case_id, path=None: _external_case(
            "qualification_key_issued"
        ),
    )

    monkeypatch.setattr(
        sync,
        "load_external_connectivity_case_store",
        lambda path=None: SimpleNamespace(
            qualification_keys=(),
            sandbox_api_keys=(),
        ),
    )

    with pytest.raises(
        sync.EnterpriseR10LifecycleSyncError,
        match="qualification_key_reference_missing",
    ):
        sync.synchronize_enterprise_r10_binding(
            BINDING_ID,
            client_id=CLIENT_ID,
            institution_case_id=CASE_ID,
            institution_task_id=TASK_ID,
            actor=CLIENT_ID,
            binding_store_path=binding_path,
        )


def test_sync_rejects_cross_client(
    tmp_path,
) -> None:
    binding_path = tmp_path / "bindings.json"
    _binding_store(binding_path)

    with pytest.raises(
        sync.EnterpriseR10LifecycleSyncError,
        match="binding_client_mismatch",
    ):
        sync.synchronize_enterprise_r10_binding(
            BINDING_ID,
            client_id="different-client",
            institution_case_id=CASE_ID,
            institution_task_id=TASK_ID,
            actor="different-client",
            binding_store_path=binding_path,
        )
