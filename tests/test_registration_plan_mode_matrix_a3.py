from __future__ import annotations

import pytest

from processual_api.auth.registration_contracts import RegistrationMode
from processual_api.auth.registration_service import (
    validate_registration_plan_mode,
)
from processual_api.billing.public_plan_journey import (
    PLAN_DEFINITIONS,
    public_plan_journey_catalog,
    resolve_direct_registration_plan,
)

DIRECT_PLAN_IDS = tuple(
    plan["plan_id"]
    for plan in public_plan_journey_catalog()["plans"]
    if plan["registration_available"]
)


@pytest.mark.parametrize("plan_id", DIRECT_PLAN_IDS)
@pytest.mark.parametrize("billing_period", ("monthly", "annual"))
def test_each_direct_plan_has_a_complete_billing_journey(plan_id: str, billing_period: str) -> None:
    resolved = resolve_direct_registration_plan(plan_id)

    assert resolved == plan_id
    assert billing_period in public_plan_journey_catalog()["billing_periods"]
    assert PLAN_DEFINITIONS[plan_id]["account_type"] in {"individual", "organization"}


@pytest.mark.parametrize("plan_id", DIRECT_PLAN_IDS)
def test_each_direct_plan_accepts_only_its_declared_account_type(plan_id: str) -> None:
    expected_mode = RegistrationMode(PLAN_DEFINITIONS[plan_id]["account_type"])
    opposite_mode = (
        RegistrationMode.ORGANIZATION
        if expected_mode is RegistrationMode.INDIVIDUAL
        else RegistrationMode.INDIVIDUAL
    )

    validate_registration_plan_mode(
        mode=expected_mode,
        selected_plan_id=plan_id,
    )

    with pytest.raises(
        ValueError,
        match="Selected plan is not available for this registration mode",
    ):
        validate_registration_plan_mode(
            mode=opposite_mode,
            selected_plan_id=plan_id,
        )


def test_missing_plan_remains_valid_for_legacy_registration() -> None:
    validate_registration_plan_mode(
        mode=RegistrationMode.INDIVIDUAL,
        selected_plan_id=None,
    )
