from __future__ import annotations

import pytest

from processual_api.services.controlled_real_pilot import (
    ControlledRealPilotAdmissionError,
    ControlledRealPilotGrant,
    KILL_SWITCH_ENV,
    PILOT_ENABLED_ENV,
    READS_ENABLED_ENV,
    WRITES_ENABLED_ENV,
    admit_controlled_real_pilot_request,
    controlled_real_pilot_status,
)


def _read_grant() -> ControlledRealPilotGrant:
    return ControlledRealPilotGrant(
        grant_id="pilot-read-1",
        task_id="crm.customer_context",
        binding_id="pilot.crm.customer_context",
        destination_host="api.customer.example",
        method="GET",
        operation_class="read",
        resource_ids=frozenset({"customer-123"}),
        writable_fields=frozenset(),
    )


def _write_grant() -> ControlledRealPilotGrant:
    return ControlledRealPilotGrant(
        grant_id="pilot-write-1",
        task_id="crm.customer_update",
        binding_id="pilot.crm.customer_update",
        destination_host="api.customer.example",
        method="PATCH",
        operation_class="approval_gated_write",
        resource_ids=frozenset({"customer-123"}),
        writable_fields=frozenset({"segment"}),
        max_mutations=1,
    )


def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        PILOT_ENABLED_ENV,
        READS_ENABLED_ENV,
        WRITES_ENABLED_ENV,
        KILL_SWITCH_ENV,
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_fail_closed_and_separate_from_external_evaluation(monkeypatch) -> None:
    _clear_env(monkeypatch)
    status = controlled_real_pilot_status()
    assert status == {
        "enabled": False,
        "reads_enabled": False,
        "writes_enabled": False,
        "kill_switch_engaged": True,
        "external_evaluation_can_enable": False,
        "default_fail_closed": True,
        "production_pilot_authority_separate": True,
        "max_mutations_per_request": 5,
    }

    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_disabled",
    ):
        admit_controlled_real_pilot_request(
            _read_grant(),
            task_id="crm.customer_context",
            binding_id="pilot.crm.customer_context",
            destination_host="api.customer.example",
            method="GET",
            operation_class="read",
            resource_id="customer-123",
        )


def test_kill_switch_blocks_even_when_pilot_and_reads_are_enabled(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(PILOT_ENABLED_ENV, "true")
    monkeypatch.setenv(READS_ENABLED_ENV, "true")
    monkeypatch.setenv(KILL_SWITCH_ENV, "true")

    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_kill_switch_engaged",
    ):
        admit_controlled_real_pilot_request(
            _read_grant(),
            task_id="crm.customer_context",
            binding_id="pilot.crm.customer_context",
            destination_host="api.customer.example",
            method="GET",
            operation_class="read",
            resource_id="customer-123",
        )


def test_read_only_pilot_requires_exact_authority_and_never_mutates(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(PILOT_ENABLED_ENV, "true")
    monkeypatch.setenv(READS_ENABLED_ENV, "true")
    monkeypatch.setenv(KILL_SWITCH_ENV, "false")

    admitted = admit_controlled_real_pilot_request(
        _read_grant(),
        task_id="crm.customer_context",
        binding_id="pilot.crm.customer_context",
        destination_host="api.customer.example",
        method="GET",
        operation_class="read",
        resource_id="customer-123",
    )
    assert admitted["admitted"] is True
    assert admitted["mode"] == "real_read_only"
    assert admitted["network_execution_performed"] is False
    assert admitted["production_mutation_performed"] is False
    assert admitted["external_evaluation_authority_reused"] is False

    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_destination_outside_grant",
    ):
        admit_controlled_real_pilot_request(
            _read_grant(),
            task_id="crm.customer_context",
            binding_id="pilot.crm.customer_context",
            destination_host="unexpected.example",
            method="GET",
            operation_class="read",
            resource_id="customer-123",
        )

    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_resource_outside_grant",
    ):
        admit_controlled_real_pilot_request(
            _read_grant(),
            task_id="crm.customer_context",
            binding_id="pilot.crm.customer_context",
            destination_host="api.customer.example",
            method="GET",
            operation_class="read",
            resource_id="customer-999",
        )


def test_write_pilot_requires_separate_switch_approval_field_and_mutation_limit(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(PILOT_ENABLED_ENV, "true")
    monkeypatch.setenv(READS_ENABLED_ENV, "true")
    monkeypatch.setenv(KILL_SWITCH_ENV, "false")

    kwargs = dict(
        task_id="crm.customer_update",
        binding_id="pilot.crm.customer_update",
        destination_host="api.customer.example",
        method="PATCH",
        operation_class="approval_gated_write",
        resource_id="customer-123",
        changed_fields={"segment"},
        requested_mutations=1,
        supervisor_approval_reference="approval-123",
    )

    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_writes_disabled",
    ):
        admit_controlled_real_pilot_request(_write_grant(), **kwargs)

    monkeypatch.setenv(WRITES_ENABLED_ENV, "true")

    without_approval = dict(kwargs)
    without_approval["supervisor_approval_reference"] = ""
    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_supervisor_approval_required",
    ):
        admit_controlled_real_pilot_request(_write_grant(), **without_approval)

    bad_field = dict(kwargs)
    bad_field["changed_fields"] = {"email"}
    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_field_outside_grant",
    ):
        admit_controlled_real_pilot_request(_write_grant(), **bad_field)

    too_many = dict(kwargs)
    too_many["requested_mutations"] = 2
    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_mutation_limit_exceeded",
    ):
        admit_controlled_real_pilot_request(_write_grant(), **too_many)

    admitted = admit_controlled_real_pilot_request(_write_grant(), **kwargs)
    assert admitted["mode"] == "approval_gated_write"
    assert admitted["supervisor_approval_reference_present"] is True
    assert admitted["network_execution_performed"] is False
    assert admitted["production_mutation_performed"] is False
    assert admitted["next_stage"] == "controlled_real_pilot_executor"


def test_read_admission_rejects_any_mutation_shape(monkeypatch) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setenv(PILOT_ENABLED_ENV, "true")
    monkeypatch.setenv(READS_ENABLED_ENV, "true")
    monkeypatch.setenv(KILL_SWITCH_ENV, "false")

    with pytest.raises(
        ControlledRealPilotAdmissionError,
        match="controlled_real_pilot_read_must_not_mutate",
    ):
        admit_controlled_real_pilot_request(
            _read_grant(),
            task_id="crm.customer_context",
            binding_id="pilot.crm.customer_context",
            destination_host="api.customer.example",
            method="GET",
            operation_class="read",
            resource_id="customer-123",
            changed_fields={"segment"},
            requested_mutations=1,
        )
