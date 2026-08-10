from __future__ import annotations

from types import SimpleNamespace

import pytest

from processual_api.auth import organization_authority
from processual_api.auth.organization_authority import (
    OrganizationAuthority,
    OrganizationAuthorityError,
    require_organization_role,
    resolve_active_organization_authority,
    resolve_current_organization_authority,
)
from processual_api.billing.plan_capability_matrix import (
    CapabilityStatus,
    TOOL_CAPABILITIES,
    plan_can_execute,
)
from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_SPECS


class _Result:
    def __init__(self, membership):
        self._membership = membership

    def scalar_one_or_none(self):
        return self._membership


class _Session:
    def __init__(self, membership):
        self._membership = membership

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, _statement):
        return _Result(self._membership)


class _SessionFactory:
    def __init__(self, membership):
        self._membership = membership

    def __call__(self):
        return _Session(self._membership)


@pytest.mark.asyncio
async def test_business_role_is_resolved_from_active_membership(monkeypatch) -> None:
    membership = SimpleNamespace(role="organization_admin")
    monkeypatch.setattr(
        organization_authority,
        "get_session_factory",
        lambda: _SessionFactory(membership),
    )

    authority = await resolve_active_organization_authority(
        user_id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
    )

    assert authority.role == "organization_admin"
    assert authority.user_id == "11111111-1111-1111-1111-111111111111"
    assert authority.organization_id == "22222222-2222-2222-2222-222222222222"


@pytest.mark.asyncio
async def test_current_user_role_claim_is_not_authority(monkeypatch) -> None:
    membership = SimpleNamespace(role="viewer")
    monkeypatch.setattr(
        organization_authority,
        "get_session_factory",
        lambda: _SessionFactory(membership),
    )

    authority = await resolve_current_organization_authority(
        {
            "session_type": "identity_user",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "organization_id": "22222222-2222-2222-2222-222222222222",
            "role": "organization_owner",
        }
    )

    assert authority.role == "viewer"
    with pytest.raises(OrganizationAuthorityError):
        require_organization_role(authority, "organization_owner")


@pytest.mark.asyncio
async def test_missing_active_membership_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        organization_authority,
        "get_session_factory",
        lambda: _SessionFactory(None),
    )

    with pytest.raises(OrganizationAuthorityError, match="active organization membership required"):
        await resolve_active_organization_authority(
            user_id="11111111-1111-1111-1111-111111111111",
            organization_id="22222222-2222-2222-2222-222222222222",
        )


@pytest.mark.asyncio
async def test_non_identity_session_cannot_claim_business_role() -> None:
    with pytest.raises(OrganizationAuthorityError, match="identity user session required"):
        await resolve_current_organization_authority(
            {
                "session_type": "jwt",
                "user_id": "11111111-1111-1111-1111-111111111111",
                "organization_id": "22222222-2222-2222-2222-222222222222",
                "role": "organization_owner",
            }
        )


def test_business_role_gate_uses_authoritative_role() -> None:
    authority = OrganizationAuthority(
        user_id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
        role="viewer",
    )

    with pytest.raises(OrganizationAuthorityError):
        require_organization_role(
            authority,
            "organization_owner",
            "organization_admin",
        )


def test_durable_execution_remains_internal_only() -> None:
    durable = TOOL_CAPABILITIES["durable_execution_internal"]

    assert durable.status is CapabilityStatus.INTERNAL_ONLY
    assert durable.customer_executable is False
    assert durable.production_allowed is False
    assert durable.execution_surface == "/internal/execution"

    for spec in PLAN_FULFILLMENT_SPECS.values():
        assert "durable_execution_internal" not in spec.entitlement_codes

    assert plan_can_execute("business", "durable_execution_internal") is False
    assert (
        plan_can_execute(
            "enterprise_strategic",
            "durable_execution_internal",
            require_production=True,
        )
        is False
    )
