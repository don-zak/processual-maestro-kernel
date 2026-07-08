from pathlib import Path

import pytest

from processual_api.integrations.readiness_tracking import (
    ITEM_STATUS_PROVIDED,
    ITEM_STATUS_VERIFIED,
    SafeEvidenceReference,
    readiness_case_from_check,
    readiness_case_summary,
    update_readiness_case_item,
)

MODULE_PATH = Path("processual_api/integrations/readiness_tracking.py")
DOC_PATH = Path("docs/integrations/INTEGRATION_READINESS_TRACKING_11N.md")


def _sample_check() -> dict[str, object]:
    return {
        "readiness_check_id": "crm:enterprise_core_api_reference:readiness",
        "adapter_contract_id": "crm",
        "credential_profile_id": "enterprise_core_api_reference",
        "missing_inputs": ["api_documentation", "sandbox_access"],
        "missing_security_controls": ["enterprise_review", "security_review"],
    }


def test_readiness_tracking_case_is_created_from_declarative_check():
    case = readiness_case_from_check(
        _sample_check(),
        client_id="client_acme",
        request_id="request_123",
        operational_profile_id="service_integration_read_only",
        assigned_supervisor="review_supervisor",
    )

    summary = readiness_case_summary(case)

    assert case.case_id == (
        "client_acme:request_123:crm:enterprise_core_api_reference:readiness"
    )
    assert summary["client_id"] == "client_acme"
    assert summary["request_id"] == "request_123"
    assert summary["inputs_total"] == 2
    assert summary["security_controls_total"] == 2
    assert summary["status_counts"]["missing"] == 4
    assert summary["sandbox_ready"] is False
    assert summary["production_allowed"] is False
    assert summary["runtime_connector_approved"] is False
    assert summary["external_http_enabled"] is False
    assert summary["raw_secret_visible"] is False


def test_readiness_tracking_updates_items_and_adds_timeline_events():
    case = readiness_case_from_check(
        _sample_check(),
        client_id="client_acme",
        request_id="request_123",
    )
    reference = SafeEvidenceReference(
        reference_type="document_ref",
        reference_label="Customer portal document reference DOC-17",
    )

    updated = update_readiness_case_item(
        case,
        item_kind="input",
        item_key="api_documentation",
        status=ITEM_STATUS_PROVIDED,
        actor="review_supervisor",
        safe_reference=reference,
        note="Documentation reference received through approved customer portal.",
    )

    summary = readiness_case_summary(updated)

    assert summary["status_counts"]["provided"] == 1
    assert summary["status_counts"]["missing"] == 3
    assert summary["timeline_events"] == 2
    assert updated.sandbox_ready is False
    assert updated.production_allowed is False
    assert updated.runtime_connector_approved is False


def test_readiness_tracking_can_mark_case_sandbox_ready_only_after_verification():
    case = readiness_case_from_check(
        _sample_check(),
        client_id="client_acme",
        request_id="request_123",
    )

    for item_kind, item_key in (
        ("input", "api_documentation"),
        ("input", "sandbox_access"),
        ("security_control", "enterprise_review"),
        ("security_control", "security_review"),
    ):
        case = update_readiness_case_item(
            case,
            item_kind=item_kind,
            item_key=item_key,
            status=ITEM_STATUS_VERIFIED,
            actor="review_supervisor",
            safe_reference=SafeEvidenceReference(
                reference_type="manual_note",
                reference_label=f"Verified {item_key} using approved internal note.",
            ),
        )

    summary = readiness_case_summary(case)

    assert summary["sandbox_ready"] is True
    assert summary["status"] == "sandbox_ready"
    assert summary["status_counts"]["verified"] == 4
    assert summary["production_allowed"] is False
    assert summary["runtime_connector_approved"] is False
    assert summary["external_http_enabled"] is False


def test_readiness_tracking_rejects_secret_or_endpoint_references():
    with pytest.raises(ValueError):
        SafeEvidenceReference(
            reference_type="document_ref",
            reference_label="https://customer.example.internal/api",
        )

    with pytest.raises(ValueError):
        SafeEvidenceReference(
            reference_type="manual_note",
            reference_label="token=abc123",
        )


def test_readiness_tracking_docs_explain_tracking_gap_and_guardrails():
    text = DOC_PATH.read_text(encoding="utf-8")

    required = [
        "readiness_case",
        "readiness_input_status",
        "readiness_security_control_status",
        "safe_evidence_reference",
        "production_allowed=false",
        "runtime_connector_approved=false",
        "external_http_enabled=false",
        "raw_secret_visible=false",
        "no external HTTP",
        "no runtime connector",
    ]

    for marker in required:
        assert marker in text


def test_readiness_tracking_module_does_not_enable_runtime_or_external_http():
    text = MODULE_PATH.read_text(encoding="utf-8")

    forbidden = [
        "requests.get",
        "requests.post",
        "httpx",
        "urllib",
        "fetch(",
        "runtime_connector_approved=True",
        "production_allowed=True",
        "external_http_enabled=True",
        "raw_secret_visible=True",
    ]

    for marker in forbidden:
        assert marker not in text
