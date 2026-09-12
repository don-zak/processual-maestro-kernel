"""Fail-closed admission policy for a future controlled real-system pilot.

This module deliberately does not execute network calls. It provides a separate
production-pilot authority boundary that cannot be inferred from, or enabled by,
External Evaluation grants. All switches default to disabled and the kill switch
defaults to engaged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

PILOT_ENABLED_ENV = "MAESTRO_CONTROLLED_REAL_PILOT_ENABLED"
READS_ENABLED_ENV = "MAESTRO_CONTROLLED_REAL_PILOT_READS_ENABLED"
WRITES_ENABLED_ENV = "MAESTRO_CONTROLLED_REAL_PILOT_WRITES_ENABLED"
KILL_SWITCH_ENV = "MAESTRO_CONTROLLED_REAL_PILOT_KILL_SWITCH"

_READ_METHODS = frozenset({"GET", "HEAD"})
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_MAX_MUTATIONS_PER_REQUEST = 5


def _env_true(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def controlled_real_pilot_status() -> dict[str, Any]:
    enabled = _env_true(PILOT_ENABLED_ENV)
    reads_enabled = enabled and _env_true(READS_ENABLED_ENV)
    writes_enabled = enabled and _env_true(WRITES_ENABLED_ENV)
    kill_switch_engaged = _env_true(KILL_SWITCH_ENV, default=True)
    return {
        "enabled": enabled,
        "reads_enabled": reads_enabled,
        "writes_enabled": writes_enabled,
        "kill_switch_engaged": kill_switch_engaged,
        "external_evaluation_can_enable": False,
        "default_fail_closed": True,
        "production_pilot_authority_separate": True,
        "max_mutations_per_request": _MAX_MUTATIONS_PER_REQUEST,
    }


@dataclass(frozen=True, slots=True)
class ControlledRealPilotGrant:
    grant_id: str
    task_id: str
    binding_id: str
    destination_host: str
    method: str
    operation_class: str
    resource_ids: frozenset[str]
    writable_fields: frozenset[str]
    max_mutations: int = 0
    supervisor_approval_required: bool = True
    active: bool = True


class ControlledRealPilotAdmissionError(ValueError):
    """A real-system pilot request was rejected before any network side effect."""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def admit_controlled_real_pilot_request(
    grant: ControlledRealPilotGrant,
    *,
    task_id: str,
    binding_id: str,
    destination_host: str,
    method: str,
    operation_class: str,
    resource_id: str,
    changed_fields: set[str] | frozenset[str] | None = None,
    requested_mutations: int = 0,
    supervisor_approval_reference: str | None = None,
) -> dict[str, Any]:
    status = controlled_real_pilot_status()
    if not status["enabled"]:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_disabled")
    if status["kill_switch_engaged"]:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_kill_switch_engaged")
    if not grant.active:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_grant_inactive")

    normalized_method = _clean(method).upper()
    normalized_task = _clean(task_id).lower()
    normalized_binding = _clean(binding_id)
    normalized_host = _clean(destination_host).lower()
    normalized_operation = _clean(operation_class)
    normalized_resource = _clean(resource_id)
    approval = _clean(supervisor_approval_reference)
    fields = frozenset(_clean(field) for field in (changed_fields or set()) if _clean(field))

    if normalized_task != grant.task_id.lower():
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_task_outside_grant")
    if normalized_binding != grant.binding_id:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_binding_outside_grant")
    if normalized_host != grant.destination_host.lower():
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_destination_outside_grant")
    if normalized_method != grant.method.upper():
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_method_outside_grant")
    if normalized_operation != grant.operation_class:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_operation_outside_grant")
    if normalized_resource not in grant.resource_ids:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_resource_outside_grant")

    if normalized_method in _READ_METHODS:
        if not status["reads_enabled"]:
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_reads_disabled")
        if requested_mutations != 0 or fields:
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_read_must_not_mutate")
        mode = "real_read_only"
    elif normalized_method in _WRITE_METHODS:
        if not status["writes_enabled"]:
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_writes_disabled")
        if grant.supervisor_approval_required and not approval:
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_supervisor_approval_required")
        if requested_mutations < 1:
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_mutation_count_required")
        allowed_mutations = min(max(grant.max_mutations, 0), _MAX_MUTATIONS_PER_REQUEST)
        if requested_mutations > allowed_mutations:
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_mutation_limit_exceeded")
        if not fields or not fields.issubset(grant.writable_fields):
            raise ControlledRealPilotAdmissionError("controlled_real_pilot_field_outside_grant")
        mode = "approval_gated_write"
    else:
        raise ControlledRealPilotAdmissionError("controlled_real_pilot_method_not_supported")

    return {
        "admitted": True,
        "mode": mode,
        "grant_id": grant.grant_id,
        "task_id": grant.task_id,
        "binding_id": grant.binding_id,
        "destination_host": grant.destination_host,
        "method": grant.method.upper(),
        "operation_class": grant.operation_class,
        "resource_id": normalized_resource,
        "requested_mutations": requested_mutations,
        "changed_fields": sorted(fields),
        "supervisor_approval_reference_present": bool(approval),
        "kill_switch_engaged": False,
        "external_evaluation_authority_reused": False,
        "network_execution_performed": False,
        "production_mutation_performed": False,
        "next_stage": "controlled_real_pilot_executor",
    }


__all__ = [
    "ControlledRealPilotAdmissionError",
    "ControlledRealPilotGrant",
    "KILL_SWITCH_ENV",
    "PILOT_ENABLED_ENV",
    "READS_ENABLED_ENV",
    "WRITES_ENABLED_ENV",
    "admit_controlled_real_pilot_request",
    "controlled_real_pilot_status",
]
