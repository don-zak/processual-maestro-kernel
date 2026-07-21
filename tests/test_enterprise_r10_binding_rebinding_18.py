from pathlib import Path

import pytest

from processual_api.services.enterprise_r10_binding_store_18 import (
    EnterpriseR10BindingStoreError,
    list_safe_enterprise_r10_bindings,
    load_enterprise_r10_binding_store,
    record_enterprise_r10_binding,
    update_enterprise_r10_binding_references,
)


def _plan() -> dict[str, object]:
    return {
        "binding_status": "validated",
        "institution_case_id": "icase_demo",
        "institution_task_id": "sandbox_capability_probe",
        "qualification_grant_id": "qgrant_demo",
        "client_id": "client_demo",
        "integration_track": "camara",
        "external_connectivity_case_id": "eccase_demo",
        "connector_id": "telecom_crm_reference",
        "operational_profile_id": (
            "enterprise_telecom_conformance_read"
        ),
        "target_environment": "sandbox",
        "requested_scope_ids": ("crm:read",),
        "external_case_state": "readiness_approved",
        "next_required_state": "qualification_key",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }


def _close_binding(
    binding_id: str,
    *,
    status: str,
    path: Path,
) -> dict[str, object]:
    return update_enterprise_r10_binding_references(
        binding_id,
        external_case_state="readiness_approved",
        next_required_state="qualification_key",
        status=status,
        actor="supsk_demo_id",
        path=path,
    )


def test_binding_identity_is_unique_and_versioned(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    first = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    assert first["binding_id"].startswith("er10bind_")
    assert first["revision"] == 1
    assert first["previous_binding_id"] is None

    _close_binding(
        first["binding_id"],
        status="revoked",
        path=path,
    )

    second = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    assert second["binding_id"].startswith("er10bind_")
    assert second["binding_id"] != first["binding_id"]
    assert second["revision"] == 2
    assert (
        second["previous_binding_id"]
        == first["binding_id"]
    )


def test_superseded_binding_can_be_replaced(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    first = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    _close_binding(
        first["binding_id"],
        status="superseded",
        path=path,
    )

    second = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    assert second["binding_id"] != first["binding_id"]
    assert second["revision"] == 2
    assert (
        second["previous_binding_id"]
        == first["binding_id"]
    )


def test_active_binding_still_blocks_duplicate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    with pytest.raises(
        EnterpriseR10BindingStoreError,
        match="active_task_binding_already_exists",
    ):
        record_enterprise_r10_binding(
            _plan(),
            actor="supsk_demo_id",
            path=path,
        )


def test_rebinding_history_and_audit_are_secret_free(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    first = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    _close_binding(
        first["binding_id"],
        status="revoked",
        path=path,
    )

    second = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    bindings = list_safe_enterprise_r10_bindings(
        institution_case_id="icase_demo",
        institution_task_id="sandbox_capability_probe",
        path=path,
    )

    assert len(bindings) == 2
    assert bindings[0]["revision"] == 1
    assert bindings[1]["revision"] == 2
    assert (
        bindings[1]["previous_binding_id"]
        == bindings[0]["binding_id"]
    )

    store = load_enterprise_r10_binding_store(path)
    serialized = str(store).lower()

    for forbidden in (
        "raw_key",
        "key_hash",
        "authorization",
        "client_secret",
        "supervisor_session_key",
    ):
        assert forbidden not in serialized

    creation_events = [
        event
        for event in store["audit"]
        if event.get("event")
        == "enterprise_r10_binding_created"
    ]

    assert len(creation_events) == 2
    assert creation_events[0]["revision"] == 1
    assert creation_events[1]["revision"] == 2
    assert (
        creation_events[1]["previous_binding_id"]
        == first["binding_id"]
    )
    assert second["raw_secret_visible"] is False
