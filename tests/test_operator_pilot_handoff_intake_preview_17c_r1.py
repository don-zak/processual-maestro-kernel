from __future__ import annotations

import pytest

from processual_api.services.operator_pilot_handoff_intake_preview import (
    IntakePreviewValidationError,
    build_operator_pilot_handoff_intake_preview,
)


def _complete_manifest() -> dict[str, object]:
    return {
        "manifest_version": "pilot-handoff-intake-17c-r1",
        "organization": {
            "organization_id": "org_ooredoo_tn_reference",
            "display_name": "Telecom operator pilot",
            "sector": "telecom",
            "technical_contact_ref": "contact://integration-team",
        },
        "integration": {
            "adapter_contract_id": "ticketing_adapter_reference",
            "credential_profile_id": "telecom_operations_api_reference",
            "target_environment": "sandbox",
            "api_documentation_ref": "document://api-guide-v1",
            "sandbox_base_url_ref": "target://telecom-sandbox",
            "authentication_method": "oauth2_client_credentials_reference",
            "requested_scopes": ["ticketing:read", "ticketing:write"],
            "sample_payload_refs": ["evidence://ticket-create-sample"],
        },
        "network_security": {
            "dns_names": ["sandbox.example.invalid"],
            "tls_min_version": "1.2",
            "outbound_allowlist_refs": ["allowlist://telecom-sandbox-v1"],
        },
        "operations": {
            "rate_limit_ref": "policy://rate-limit-v1",
            "support_contact_ref": "contact://pilot-support",
            "maintenance_window_ref": "window://sandbox-pilot",
        },
        "governance": {
            "data_classification": "restricted_metadata_only",
            "retention_policy_ref": "policy://retention-v1",
            "incident_contact_ref": "contact://security-incident",
        },
        "evidence_refs": ["evidence://operator-approval-request"],
    }


def test_complete_reference_manifest_is_ready_for_supervisor_review() -> None:
    preview = build_operator_pilot_handoff_intake_preview(_complete_manifest())

    assert preview["status"] == "ready_for_supervisor_review"
    assert preview["completeness_percent"] == 100
    assert preview["missing_fields"] == []
    assert preview["manifest_digest"].startswith("sha256:")
    assert preview["persisted"] is False
    assert preview["review_only"] is True
    assert preview["next_action"] == "Supervisor reviews references and evidence before sandbox qualification."
    assert all(value is False for value in preview["guardrails"].values())


def test_incomplete_manifest_returns_exact_missing_fields() -> None:
    manifest = _complete_manifest()
    del manifest["integration"]["api_documentation_ref"]  # type: ignore[index]
    del manifest["network_security"]["outbound_allowlist_refs"]  # type: ignore[index]

    preview = build_operator_pilot_handoff_intake_preview(manifest)

    assert preview["status"] == "needs_input"
    assert preview["completeness_percent"] < 100
    assert "integration.api_documentation_ref" in preview["missing_fields"]
    assert "network_security.outbound_allowlist_refs" in preview["missing_fields"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("integration", "client_secret"), "do-not-store"),
        (("integration", "api_key"), "do-not-store"),
        (("network_security", "authorization"), "Bearer hidden"),
        (("operations", "password"), "do-not-store"),
    ],
)
def test_manifest_rejects_secret_bearing_fields(path: tuple[str, str], value: str) -> None:
    manifest = _complete_manifest()
    section, field = path
    manifest[section][field] = value  # type: ignore[index]

    with pytest.raises(IntakePreviewValidationError, match="prohibited"):
        build_operator_pilot_handoff_intake_preview(manifest)


def test_manifest_rejects_production_target_and_unknown_top_level_fields() -> None:
    manifest = _complete_manifest()
    manifest["integration"]["target_environment"] = "production"  # type: ignore[index]

    with pytest.raises(IntakePreviewValidationError, match="sandbox"):
        build_operator_pilot_handoff_intake_preview(manifest)

    manifest = _complete_manifest()
    manifest["unexpected"] = {"field": "value"}

    with pytest.raises(IntakePreviewValidationError, match="unknown top-level"):
        build_operator_pilot_handoff_intake_preview(manifest)


def test_preview_does_not_echo_manifest_or_contact_values() -> None:
    preview = build_operator_pilot_handoff_intake_preview(_complete_manifest())
    rendered = repr(preview)

    assert "sandbox.example.invalid" not in rendered
    assert "contact://integration-team" not in rendered
    assert "requested_scopes" not in preview
    assert "manifest" not in preview

