from __future__ import annotations

import pytest

import processual_api.services.enterprise_r10_controlled_sandbox_18 as sandbox


def _binding() -> dict[str, object]:
    return {
        "binding_id": "er10bind_q2br8",
        "revision": 3,
        "institution_case_id": "institution_case_q2br8",
        "institution_task_id": "ticket_read_q2br8",
        "qualification_grant_id": "qgrant_q2br8",
        "client_id": "client_q2br8",
        "external_connectivity_case_id": "external_case_q2br8",
        "connector_id": "telecom_ticketing_reference",
        "operational_profile_id": "sandbox-read-only",
        "target_environment": "sandbox",
        "requested_scope_ids": ["ticket:read"],
        "external_case_state": "sandbox_api_key_issued",
        "next_required_state": "controlled_sandbox_dispatcher",
        "external_qualification_key_id": "ecqk_q2br8",
        "external_sandbox_api_key_id": "ecsbk_q2br8",
        "status": "sandbox_api_key_issued",
        "updated_at": "2026-07-20T12:00:00+00:00",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }


def _run(
    monkeypatch: pytest.MonkeyPatch,
    binding: dict[str, object],
) -> dict[str, object]:
    monkeypatch.setattr(
        sandbox,
        "list_safe_enterprise_r10_bindings",
        lambda path=None: [binding],
    )

    return sandbox.qualify_enterprise_r10_controlled_sandbox(
        "er10bind_q2br8",
        client_id="client_q2br8",
        institution_case_id="institution_case_q2br8",
        institution_task_id="ticket_read_q2br8",
    )


def test_controlled_local_qualification_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _run(monkeypatch, _binding())

    assert result["status"] == (
        "synthetic_qualification_completed"
    )
    assert result["connector_id"] == (
        "telecom_ticketing_reference"
    )
    assert result["scope_id"] == "ticket:read"
    assert result[
        "sandbox_api_key_reference_verified"
    ] is True
    assert result["workflow"]["status"] == (
        "synthetic_read_completed"
    )
    assert result["evidence"][
        "evidence_captured"
    ] is True
    assert result["evidence"]["reference_only"] is True
    assert result["evidence"]["local_only"] is True


@pytest.mark.parametrize(
    "field_name",
    (
        "sandbox_api_key_value_received",
        "sandbox_api_key_value_returned",
        "credential_resolved",
        "dispatcher_invoked",
        "real_transport_attempted",
        "operation_executed",
        "external_http_used",
        "socket_used",
        "payload_persisted",
        "runtime_used",
        "production_used",
    ),
)
def test_controlled_local_qualification_stays_disabled(
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
) -> None:
    result = _run(monkeypatch, _binding())

    assert result[field_name] is False


def test_wrong_connector_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding()
    binding["connector_id"] = "telecom_crm_reference"

    with pytest.raises(
        sandbox.EnterpriseR10ControlledSandboxError,
        match=(
            "connector_not_supported_by_local_workflow"
        ),
    ):
        _run(monkeypatch, binding)


def test_non_exact_scope_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding()
    binding["requested_scope_ids"] = [
        "ticket:read",
        "ticket:write",
    ]

    with pytest.raises(
        sandbox.EnterpriseR10ControlledSandboxError,
        match="binding_scope_not_exact_ticket_read",
    ):
        _run(monkeypatch, binding)


def test_missing_sandbox_key_reference_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding()
    binding["external_sandbox_api_key_id"] = None

    with pytest.raises(
        sandbox.EnterpriseR10ControlledSandboxError,
        match="sandbox_api_key_reference_missing",
    ):
        _run(monkeypatch, binding)


def test_unsafe_binding_flag_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = _binding()
    binding["external_http_allowed"] = True

    with pytest.raises(
        sandbox.EnterpriseR10ControlledSandboxError,
        match="binding_guardrail_violation",
    ):
        _run(monkeypatch, binding)
