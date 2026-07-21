import json
from pathlib import Path

import pytest

from processual_api.services.enterprise_r10_binding_store_18 import (
    EnterpriseR10BindingStoreError,
    empty_enterprise_r10_binding_store,
    list_safe_enterprise_r10_bindings,
    load_enterprise_r10_binding_store,
    record_enterprise_r10_binding,
    save_enterprise_r10_binding_store,
    update_enterprise_r10_binding_references,
)


def _plan() -> dict:
    return {
        "binding_status": "validated",
        "institution_case_id": "icase_demo",
        "institution_task_id": (
            "sandbox_capability_probe"
        ),
        "qualification_grant_id": (
            "qgrant_demo"
        ),
        "client_id": "client_demo",
        "integration_track": "camara",
        "external_connectivity_case_id": (
            "eccase_demo"
        ),
        "connector_id": "camara_reference",
        "operational_profile_id": (
            "telecom_operations_api_reference"
        ),
        "target_environment": "sandbox",
        "requested_scope_ids": (
            "capability:read",
        ),
        "connector_scope_ids": (
            "capability:read",
            "consent:read",
        ),
        "external_case_state": (
            "readiness_approved"
        ),
        "next_required_state": (
            "qualification_key"
        ),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }


def test_empty_binding_store_is_versioned(
    tmp_path: Path,
) -> None:
    result = load_enterprise_r10_binding_store(
        tmp_path / "bindings.json"
    )

    assert (
        result
        == empty_enterprise_r10_binding_store()
    )


@pytest.mark.parametrize(
    "forbidden_key",
    (
        "api_key",
        "sandbox_api_key",
        "qualification_key",
        "raw_key",
        "key_hash",
        "authorization",
        "client_secret",
        "supervisor_session_key",
    ),
)
def test_store_rejects_credential_material(
    tmp_path: Path,
    forbidden_key: str,
) -> None:
    path = tmp_path / "bindings.json"
    store = empty_enterprise_r10_binding_store()

    store["bindings"].append(
        {
            "binding_id": "binding_demo",
            forbidden_key: "forbidden",
        }
    )

    with pytest.raises(
        EnterpriseR10BindingStoreError,
        match="Credential material is forbidden",
    ):
        save_enterprise_r10_binding_store(
            store,
            path,
        )

    assert not path.exists()


def test_valid_binding_is_persisted_without_secrets(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    result = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    assert result["status"] == "validated"
    assert result["institution_case_id"] == (
        "icase_demo"
    )
    assert result["institution_task_id"] == (
        "sandbox_capability_probe"
    )
    assert (
        result["external_connectivity_case_id"]
        == "eccase_demo"
    )

    assert (
        result["external_qualification_key_id"]
        is None
    )
    assert (
        result["external_sandbox_api_key_id"]
        is None
    )

    assert result["production_allowed"] is False
    assert (
        result["runtime_connector_approved"]
        is False
    )
    assert result["raw_secret_visible"] is False

    serialized = path.read_text(
        encoding="utf-8"
    ).lower()

    assert '"raw_key"' not in serialized
    assert '"key_hash"' not in serialized
    assert '"authorization"' not in serialized
    assert '"supervisor_session_key"' not in serialized

    stored = json.loads(serialized)

    assert len(stored["bindings"]) == 1
    assert len(stored["audit"]) == 1


def test_unvalidated_plan_is_rejected(
    tmp_path: Path,
) -> None:
    plan = _plan()
    plan["binding_status"] = "blocked"

    with pytest.raises(
        EnterpriseR10BindingStoreError,
        match="binding_plan_not_validated",
    ):
        record_enterprise_r10_binding(
            plan,
            actor="supsk_demo_id",
            path=tmp_path / "bindings.json",
        )


def test_unsafe_plan_is_rejected(
    tmp_path: Path,
) -> None:
    plan = _plan()
    plan["production_allowed"] = True

    with pytest.raises(
        EnterpriseR10BindingStoreError,
        match="unsafe_binding_plan",
    ):
        record_enterprise_r10_binding(
            plan,
            actor="supsk_demo_id",
            path=tmp_path / "bindings.json",
        )


def test_duplicate_active_task_binding_is_rejected(
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


def test_binding_lifecycle_references_can_be_updated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    created = record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    updated = (
        update_enterprise_r10_binding_references(
            created["binding_id"],
            external_case_state=(
                "qualification_key_issued"
            ),
            next_required_state=(
                "qualification_redemption"
            ),
            external_qualification_key_id=(
                "ecqk_demo"
            ),
            status="qualification_key_issued",
            actor="supsk_demo_id",
            path=path,
        )
    )

    assert updated["status"] == (
        "qualification_key_issued"
    )
    assert (
        updated["external_qualification_key_id"]
        == "ecqk_demo"
    )
    assert (
        updated["external_sandbox_api_key_id"]
        is None
    )

    assert updated["production_allowed"] is False
    assert updated["raw_secret_visible"] is False


def test_client_listing_is_isolated(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bindings.json"

    record_enterprise_r10_binding(
        _plan(),
        actor="supsk_demo_id",
        path=path,
    )

    matching = list_safe_enterprise_r10_bindings(
        client_id="client_demo",
        institution_case_id="icase_demo",
        path=path,
    )

    other_client = list_safe_enterprise_r10_bindings(
        client_id="client_other",
        path=path,
    )

    assert len(matching) == 1
    assert other_client == []

    serialized = repr(matching).lower()

    assert "raw_key" not in serialized
    assert "key_hash" not in serialized
    assert "supervisor_session_key" not in serialized
