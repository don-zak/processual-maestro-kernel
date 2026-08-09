import uuid
from datetime import UTC, datetime

from processual_api.admin_marketplace.subscription_access import SubscriptionAccessSnapshot
from processual_api.middleware.subscription import (
    _enforce_server_authoritative_capability,
    _required_server_authoritative_capability,
)


def _access(*, plan_code: str) -> SubscriptionAccessSnapshot:
    return SubscriptionAccessSnapshot(
        runtime_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        subscription_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        customer_ref="institution-acme",
        access_stage="active",
        plan_code=plan_code,
        entitlement_profile_ref="academic-entitlements-v1",
        quota_profile_ref="assessment_quota_aaaaaaaaaaaaaaaaaaaaaaaa",
        effective_at=datetime(2026, 8, 9, 20, 0, tzinfo=UTC),
        grace_until=None,
    )


def test_cgt_govern_declares_maestro_execution_capability() -> None:
    assert (
        _required_server_authoritative_capability(
            method="POST",
            path="/cgt/govern",
        )
        == "maestro_execution"
    )
    assert (
        _required_server_authoritative_capability(
            method="POST",
            path="/cgt/govern/",
        )
        == "maestro_execution"
    )


def test_server_authoritative_academic_entitlement_allows_maestro_execution() -> None:
    denial = _enforce_server_authoritative_capability(
        access=_access(plan_code="academic"),
        method="POST",
        path="/cgt/govern",
    )

    assert denial is None


def test_unknown_server_plan_fails_closed_for_paid_capability() -> None:
    denial = _enforce_server_authoritative_capability(
        access=_access(plan_code="unknown-paid-plan"),
        method="POST",
        path="/cgt/govern",
    )

    assert denial is not None
    assert denial.status_code == 403
    assert b"Subscription plan does not permit this operation." in denial.body


def test_unmapped_route_is_not_given_an_invented_capability_requirement() -> None:
    assert (
        _required_server_authoritative_capability(
            method="POST",
            path="/reports/export",
        )
        is None
    )
    denial = _enforce_server_authoritative_capability(
        access=_access(plan_code="unknown-paid-plan"),
        method="POST",
        path="/reports/export",
    )
    assert denial is None
