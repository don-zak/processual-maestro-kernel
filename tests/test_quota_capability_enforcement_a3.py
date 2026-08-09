import pytest
from fastapi import HTTPException

from processual_api.services import quota_store


def test_authoritative_plan_capability_allows_counted_governance_endpoint() -> None:
    quota_store._enforce_authoritative_capability(
        plan_id="business",
        policy={"source": "authoritative_fulfillment_catalog"},
        method="POST",
        endpoint="/cgt/govern",
    )


def test_authoritative_capability_denial_is_fail_closed(monkeypatch) -> None:
    class DeniedError(PermissionError):
        pass

    monkeypatch.setattr(quota_store, "PlanEntitlementDeniedError", DeniedError)

    def deny(*args, **kwargs):
        raise DeniedError("denied")

    monkeypatch.setattr(quota_store, "require_plan_entitlement", deny)

    with pytest.raises(HTTPException) as captured:
        quota_store._enforce_authoritative_capability(
            plan_id="business",
            policy={"source": "authoritative_fulfillment_catalog"},
            method="POST",
            endpoint="/cgt/govern",
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == "Subscription plan does not permit this operation."


def test_legacy_policy_is_not_forced_through_new_entitlement_contract(monkeypatch) -> None:
    called = False

    def should_not_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(quota_store, "require_plan_entitlement", should_not_run)

    quota_store._enforce_authoritative_capability(
        plan_id="pilot_pro",
        policy={"source": "legacy_plan"},
        method="POST",
        endpoint="/cgt/govern",
    )

    assert called is False


def test_manual_policy_is_not_forced_through_new_entitlement_contract(monkeypatch) -> None:
    called = False

    def should_not_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(quota_store, "require_plan_entitlement", should_not_run)

    quota_store._enforce_authoritative_capability(
        plan_id="starter",
        policy={"source": "manual"},
        method="POST",
        endpoint="/cgt/govern",
    )

    assert called is False


def test_counted_endpoint_has_declared_capability() -> None:
    assert quota_store.COUNTED_ENDPOINT_CAPABILITIES == {
        ("POST", "/cgt/govern"): "maestro_execution"
    }
    assert quota_store.COUNTED_ENDPOINTS == set(
        quota_store.COUNTED_ENDPOINT_CAPABILITIES
    )
