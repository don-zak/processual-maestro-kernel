from __future__ import annotations

from datetime import UTC, datetime

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.credential_profiles import (
    COMMON_REQUIRED_CUSTOMER_INPUTS,
    get_credential_profile,
)
from processual_api.integrations.enterprise_qualification_drafts import (
    DRAFT_STORAGE_KEY,
    safe_qualification_draft,
    save_qualification_draft,
    submit_qualification_draft,
)


def _profile_id() -> str:
    return "enterprise_core_api_reference"


def _scope_id() -> str:
    profile = get_credential_profile(_profile_id())
    for contract_id in profile.adapter_contract_ids:
        contract = get_adapter_contract(contract_id)
        if contract.required_scopes:
            return contract.required_scopes[0]
    raise AssertionError("profile has no required scope")


def test_save_draft_persists_identifiers_and_lifecycle_metadata_only() -> None:
    raw: dict = {"subscription": {"plan_id": "enterprise_core"}}
    payload = save_qualification_draft(
        raw,
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[COMMON_REQUIRED_CUSTOMER_INPUTS[0]],
        now=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )

    stored = raw[DRAFT_STORAGE_KEY]
    assert set(stored) == {
        "schema_version",
        "status",
        "revision",
        "credential_profile_id",
        "requested_scope_ids",
        "provided_input_ids",
        "created_at",
        "updated_at",
    }
    assert stored["status"] == "draft"
    assert stored["revision"] == 1
    assert stored["credential_profile_id"] == _profile_id()
    assert stored["requested_scope_ids"] == [_scope_id()]
    assert stored["provided_input_ids"] == [COMMON_REQUIRED_CUSTOMER_INPUTS[0]]
    assert payload["persisted"] is True
    assert payload["draft_status"] == "draft"
    assert payload["security_controls_approved"] == 0
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False

    serialized = repr(stored).lower()
    assert "credential_value" not in serialized
    assert "client_secret" not in serialized
    assert "access_token" not in serialized
    assert "endpoint_url" not in serialized
    assert "security_controls_approved" not in serialized


def test_saved_draft_revalidates_against_current_catalog_and_fails_closed() -> None:
    raw: dict = {}
    save_qualification_draft(
        raw,
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[],
    )
    raw[DRAFT_STORAGE_KEY]["requested_scope_ids"] = ["removed:scope"]

    assert safe_qualification_draft(raw) is None


def test_saving_again_increments_revision_and_preserves_creation_time() -> None:
    raw: dict = {}
    first = save_qualification_draft(
        raw,
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[],
        now=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )
    second = save_qualification_draft(
        raw,
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[COMMON_REQUIRED_CUSTOMER_INPUTS[0]],
        now=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
    )

    assert first["revision"] == 1
    assert second["revision"] == 2
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] != first["updated_at"]


def test_submit_moves_valid_draft_to_pending_review_without_approval() -> None:
    raw: dict = {}
    save_qualification_draft(
        raw,
        credential_profile_id=_profile_id(),
        requested_scope_ids=[_scope_id()],
        provided_input_ids=list(COMMON_REQUIRED_CUSTOMER_INPUTS),
        now=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )
    payload = submit_qualification_draft(
        raw,
        now=datetime(2026, 8, 9, 12, 10, tzinfo=UTC),
    )

    stored = raw[DRAFT_STORAGE_KEY]
    assert stored["status"] == "pending_review"
    assert stored["revision"] == 2
    assert stored["submitted_at"] == payload["submitted_at"]
    assert payload["draft_status"] == "pending_review"
    assert payload["missing_input_ids"] == []
    assert payload["security_controls_approved"] == 0
    assert payload["sandbox_ready"] is False
    assert payload["production_allowed"] is False
    assert payload["runtime_connector_approved"] is False


def test_invalid_stored_types_fail_closed() -> None:
    raw = {
        DRAFT_STORAGE_KEY: {
            "status": "draft",
            "credential_profile_id": _profile_id(),
            "requested_scope_ids": "not-a-list",
            "provided_input_ids": [],
        }
    }

    assert safe_qualification_draft(raw) is None
