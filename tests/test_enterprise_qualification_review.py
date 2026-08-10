from __future__ import annotations

from datetime import UTC, datetime

import pytest

from processual_api.integrations.adapter_contracts import get_adapter_contract
from processual_api.integrations.credential_profiles import get_credential_profile
from processual_api.integrations.enterprise_qualification_drafts import (
    DRAFT_STORAGE_KEY,
    save_qualification_draft,
    submit_qualification_draft,
)
from processual_api.integrations.enterprise_qualification_review import (
    REVIEW_STORAGE_KEY,
    request_qualification_revision,
    safe_qualification_review,
)


def _scope_id() -> str:
    profile = get_credential_profile("enterprise_core_api_reference")
    for contract_id in profile.adapter_contract_ids:
        contract = get_adapter_contract(contract_id)
        if contract.required_scopes:
            return contract.required_scopes[0]
    raise AssertionError("profile has no required scope")


def _pending_raw() -> dict:
    raw: dict = {}
    save_qualification_draft(
        raw,
        credential_profile_id="enterprise_core_api_reference",
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[],
        now=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    )
    submit_qualification_draft(
        raw,
        now=datetime(2026, 8, 9, 12, 5, tzinfo=UTC),
    )
    return raw


def test_revision_request_returns_pending_draft_to_editable_state() -> None:
    raw = _pending_raw()
    review = request_qualification_revision(
        raw,
        reason_code="scope_needs_clarification",
        reviewer_id="reviewer@example.test",
        now=datetime(2026, 8, 9, 12, 10, tzinfo=UTC),
    )

    assert raw[DRAFT_STORAGE_KEY]["status"] == "draft"
    assert "submitted_at" not in raw[DRAFT_STORAGE_KEY]
    assert review == {
        "status": "revision_requested",
        "reason_code": "scope_needs_clarification",
        "draft_revision": 3,
        "reviewed_at": "2026-08-09T12:10:00+00:00",
        "production_allowed": False,
        "runtime_connector_approved": False,
    }
    assert raw[REVIEW_STORAGE_KEY]["reviewer_id"] == "reviewer@example.test"
    assert "reviewer_id" not in review


def test_revision_reason_is_fixed_identifier_not_free_text() -> None:
    raw = _pending_raw()

    with pytest.raises(ValueError, match="unsupported qualification revision reason"):
        request_qualification_revision(
            raw,
            reason_code="please paste the customer secret here",
            reviewer_id="reviewer",
        )

    assert REVIEW_STORAGE_KEY not in raw


def test_revision_requires_pending_review_state() -> None:
    raw: dict = {}
    save_qualification_draft(
        raw,
        credential_profile_id="enterprise_core_api_reference",
        requested_scope_ids=[_scope_id()],
        provided_input_ids=[],
    )

    with pytest.raises(ValueError, match="not pending review"):
        request_qualification_revision(
            raw,
            reason_code="security_evidence_required",
            reviewer_id="reviewer",
        )


def test_invalid_review_storage_fails_closed() -> None:
    raw = {
        REVIEW_STORAGE_KEY: {
            "status": "revision_requested",
            "reason_code": "unknown_reason",
            "draft_revision": 2,
            "reviewed_at": "2026-08-09T12:00:00+00:00",
        }
    }

    assert safe_qualification_review(raw) is None
