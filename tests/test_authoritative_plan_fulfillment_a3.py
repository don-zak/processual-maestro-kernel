from __future__ import annotations

import pytest

from processual_api.billing.commercial_catalog_contracts import (
    build_catalog_plan_contracts,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_SPECS,
    PlanFulfillmentSpec,
    get_plan_fulfillment_spec,
)
from processual_api.billing.usage_pricing import monthly_unit_allowance


def test_commercial_catalog_matches_authoritative_fulfillment_source() -> None:
    contracts = {plan.plan_code: plan for plan in build_catalog_plan_contracts()}

    assert set(contracts) == set(PLAN_FULFILLMENT_SPECS)
    for plan_code, spec in PLAN_FULFILLMENT_SPECS.items():
        contract = contracts[plan_code]
        assert contract.included_maestro_units == spec.monthly_unit_allowance
        assert tuple(item.value for item in contract.entitlements) == (
            spec.entitlement_codes
        )
        assert spec.seat_based_consumption is False


def test_runtime_allowance_uses_authoritative_fulfillment_source() -> None:
    for plan_code, spec in PLAN_FULFILLMENT_SPECS.items():
        assert monthly_unit_allowance(plan_code) == spec.monthly_unit_allowance


def test_unknown_plan_fails_closed() -> None:
    with pytest.raises(KeyError, match="unknown authoritative plan"):
        get_plan_fulfillment_spec("unknown-plan")


def test_seat_based_consumption_is_structurally_forbidden() -> None:
    with pytest.raises(ValueError, match="quota based, not seat based"):
        PlanFulfillmentSpec(
            plan_code="invalid-seat-plan",
            monthly_unit_allowance=100,
            entitlement_codes=("maestro_execution",),
            seat_based_consumption=True,
        )
