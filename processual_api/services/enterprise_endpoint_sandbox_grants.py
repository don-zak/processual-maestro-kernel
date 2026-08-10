"""Supervisor-approved grants for Enterprise endpoint sandbox execution."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
    validate_endpoint_binding,
)
from processual_api.integrations.integration_task_catalog import get_integration_task

SANDBOX_GRANT_STORAGE_KEY = "enterprise_endpoint_sandbox_grants_v1"


class SandboxGrantError(ValueError):
    """A sandbox execution grant is invalid or unavailable."""


def _now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _stored_grants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    items = raw.get(SANDBOX_GRANT_STORAGE_KEY, [])
    return [dict(item) for item in items if isinstance(item, dict)]


def safe_grant_projection(grant: dict[str, Any]) -> dict[str, Any]:
    return {
        "grant_id": str(grant.get("grant_id") or ""),
        "binding_id": str(grant.get("binding_id") or ""),
        "task_id": str(grant.get("task_id") or ""),
        "adapter_contract_id": str(grant.get("adapter_contract_id") or ""),
        "approved_operation_classes": list(
            grant.get("approved_operation_classes") or []
        ),
        "required_scope_ids": list(grant.get("required_scope_ids") or []),
        "status": str(grant.get("status") or ""),
        "issued_at": str(grant.get("issued_at") or ""),
        "expires_at": str(grant.get("expires_at") or ""),
        "issued_by": str(grant.get("issued_by") or ""),
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


def issue_sandbox_execution_grant(
    raw: dict[str, Any],
    *,
    spec: EnterpriseEndpointBindingSpec,
    supervisor_id: str,
    ttl_minutes: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    validation = validate_endpoint_binding(spec)
    task = get_integration_task(spec.task_id)
    supervisor = str(supervisor_id or "").strip()
    if not supervisor:
        raise SandboxGrantError("supervisor identity is required")
    if ttl_minutes < 5 or ttl_minutes > 120:
        raise SandboxGrantError("sandbox grant TTL must be between 5 and 120 minutes")

    issued_at = _now(now)
    expires_at = issued_at + timedelta(minutes=ttl_minutes)
    grants = _stored_grants(raw)
    for item in grants:
        if (
            item.get("binding_id") == spec.binding_id
            and item.get("status") == "active"
        ):
            item["status"] = "superseded"

    grant = {
        "grant_id": f"segrant_{secrets.token_hex(8)}",
        "binding_id": spec.binding_id,
        "task_id": spec.task_id,
        "adapter_contract_id": spec.adapter_contract_id,
        "approved_operation_classes": [task.operation_class],
        "required_scope_ids": list(validation["required_scope_ids"]),
        "status": "active",
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "issued_by": supervisor,
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
    }
    grants.append(grant)
    raw[SANDBOX_GRANT_STORAGE_KEY] = grants
    return safe_grant_projection(grant)


def resolve_active_sandbox_execution_grant(
    raw: dict[str, Any],
    *,
    binding_id: str,
    task_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = _now(now)
    matches: list[dict[str, Any]] = []
    for grant in _stored_grants(raw):
        if grant.get("binding_id") != binding_id or grant.get("task_id") != task_id:
            continue
        if grant.get("status") != "active":
            continue
        try:
            expires_at = datetime.fromisoformat(str(grant.get("expires_at") or ""))
        except ValueError:
            continue
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at.astimezone(UTC) <= current:
            continue
        matches.append(grant)
    if len(matches) != 1:
        raise SandboxGrantError("active sandbox execution grant is required")
    return safe_grant_projection(matches[0])


__all__ = [
    "SANDBOX_GRANT_STORAGE_KEY",
    "SandboxGrantError",
    "issue_sandbox_execution_grant",
    "resolve_active_sandbox_execution_grant",
    "safe_grant_projection",
]
