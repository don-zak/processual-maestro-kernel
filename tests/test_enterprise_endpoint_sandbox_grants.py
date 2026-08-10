from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from processual_api.integrations.enterprise_endpoint_bindings import (
    EnterpriseEndpointBindingSpec,
)
from processual_api.services.enterprise_endpoint_sandbox_grants import (
    SANDBOX_GRANT_STORAGE_KEY,
    SandboxGrantError,
    issue_sandbox_execution_grant,
    resolve_active_sandbox_execution_grant,
)


def _spec() -> EnterpriseEndpointBindingSpec:
    return EnterpriseEndpointBindingSpec(
        binding_id="billing.account",
        display_name="Billing account",
        adapter_contract_id="billing",
        task_id="billing.account_context",
        credential_profile_id="enterprise_core_api_reference",
        environment="sandbox",
        base_url="https://sandbox.example.test/api",
        method="GET",
        path="/accounts/{account_id}",
        required_scope_ids=["billing:read"],
        path_parameters={"account_id": "$task.account_id"},
        field_mapping={"account_id": "$.id"},
    )


def test_grant_is_short_lived_and_exactly_bound() -> None:
    raw: dict = {}
    now = datetime(2026, 8, 10, 17, 0, tzinfo=UTC)
    grant = issue_sandbox_execution_grant(
        raw,
        spec=_spec(),
        supervisor_id="admin@example.test",
        ttl_minutes=30,
        now=now,
    )

    assert grant["binding_id"] == "billing.account"
    assert grant["task_id"] == "billing.account_context"
    assert grant["approved_operation_classes"] == ["read"]
    assert grant["required_scope_ids"] == ["billing:read"]
    assert grant["production_allowed"] is False
    assert raw[SANDBOX_GRANT_STORAGE_KEY][0]["issued_by"] == "admin@example.test"

    resolved = resolve_active_sandbox_execution_grant(
        raw,
        binding_id="billing.account",
        task_id="billing.account_context",
        now=now + timedelta(minutes=10),
    )
    assert resolved["grant_id"] == grant["grant_id"]


def test_expired_grant_is_rejected() -> None:
    raw: dict = {}
    now = datetime(2026, 8, 10, 17, 0, tzinfo=UTC)
    issue_sandbox_execution_grant(
        raw,
        spec=_spec(),
        supervisor_id="admin@example.test",
        ttl_minutes=5,
        now=now,
    )
    with pytest.raises(SandboxGrantError, match="active sandbox execution grant"):
        resolve_active_sandbox_execution_grant(
            raw,
            binding_id="billing.account",
            task_id="billing.account_context",
            now=now + timedelta(minutes=6),
        )


def test_new_grant_supersedes_previous_binding_grant() -> None:
    raw: dict = {}
    now = datetime(2026, 8, 10, 17, 0, tzinfo=UTC)
    first = issue_sandbox_execution_grant(
        raw,
        spec=_spec(),
        supervisor_id="first",
        ttl_minutes=30,
        now=now,
    )
    second = issue_sandbox_execution_grant(
        raw,
        spec=_spec(),
        supervisor_id="second",
        ttl_minutes=30,
        now=now + timedelta(minutes=1),
    )
    assert first["grant_id"] != second["grant_id"]
    assert raw[SANDBOX_GRANT_STORAGE_KEY][0]["status"] == "superseded"
    assert raw[SANDBOX_GRANT_STORAGE_KEY][1]["status"] == "active"
