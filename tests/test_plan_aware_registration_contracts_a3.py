import pytest
from pydantic import ValidationError

from processual_api.auth.registration_contracts import IndividualRegistrationRequestContract
from processual_api.billing.public_plan_journey import resolve_direct_registration_plan


def _payload(**overrides):
    payload = {
        "email": "user@example.com",
        "full_name": "Example User",
        "password": "correct-horse-battery-staple",
        "accepted_terms_version": "2026-08",
    }
    payload.update(overrides)
    return payload


def test_registration_contract_accepts_optional_selected_plan_id():
    contract = IndividualRegistrationRequestContract(**_payload(selected_plan_id="starter"))
    assert contract.selected_plan_id == "starter"


def test_registration_contract_preserves_legacy_missing_plan():
    contract = IndividualRegistrationRequestContract(**_payload())
    assert contract.selected_plan_id is None


def test_registration_contract_rejects_client_supplied_price():
    with pytest.raises(ValidationError):
        IndividualRegistrationRequestContract(**_payload(selected_plan_id="starter", monthly_price_usd="1.00"))


@pytest.mark.parametrize(
    ("plan_id", "expected"),
    [
        ("academic", "academic"),
        ("starter", "starter"),
        ("business", "business"),
        ("enterprise_integration_starter", "enterprise_integration_starter"),
        ("enterprise_pilot", "enterprise_pilot"),
        (" STARTER ", "starter"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_direct_registration_plan_resolver_accepts_public_registration_plans(plan_id, expected):
    assert resolve_direct_registration_plan(plan_id) == expected


@pytest.mark.parametrize(
    "plan_id", ["enterprise_core", "enterprise_scale", "enterprise_strategic", "unknown", "internal_admin"]
)
def test_direct_registration_plan_resolver_fails_closed(plan_id):
    with pytest.raises(ValueError):
        resolve_direct_registration_plan(plan_id)
