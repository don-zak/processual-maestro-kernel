from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint, Index

from processual_api.billing.contracts import BillingProfileUpsertRequest
from processual_api.billing.models import CustomerBillingProfile


def test_billing_profile_model_has_authoritative_identity_context() -> None:
    table = CustomerBillingProfile.__table__

    assert table.name == "customer_billing_profiles"
    assert table.c.user_id.nullable is False
    assert table.c.organization_id.nullable is True
    assert table.c.country_code.nullable is False
    assert table.c.status.nullable is False

    foreign_keys = {
        (
            foreign_key.parent.name,
            foreign_key.target_fullname,
            foreign_key.ondelete,
        )
        for foreign_key in table.foreign_keys
    }

    assert (
        "user_id",
        "identity_users.id",
        "CASCADE",
    ) in foreign_keys
    assert (
        "organization_id",
        "identity_organizations.id",
        "SET NULL",
    ) in foreign_keys


def test_billing_profile_model_has_required_constraints_and_indexes() -> None:
    table = CustomerBillingProfile.__table__

    constraints = {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)}
    indexes = {index.name for index in table.indexes if isinstance(index, Index)}

    assert "ck_customer_billing_profiles_country_code_format" in constraints
    assert "ck_customer_billing_profiles_status_allowed" in constraints
    assert "uq_customer_billing_profiles_personal" in indexes
    assert "uq_customer_billing_profiles_organization" in indexes
    assert "ix_customer_billing_profiles_country_status" in indexes


def test_billing_profile_contract_normalizes_country_code() -> None:
    request = BillingProfileUpsertRequest(
        country_code="tn",
        city=" Tunis ",
        address_line_1=" Avenue Habib Bourguiba ",
    )

    assert request.country_code == "TN"
    assert request.city == "Tunis"
    assert request.address_line_1 == "Avenue Habib Bourguiba"


@pytest.mark.parametrize(
    "country_code",
    ["T", "TUN", "12", "T1", ""],
)
def test_billing_profile_contract_rejects_invalid_country_code(
    country_code: str,
) -> None:
    with pytest.raises(ValidationError):
        BillingProfileUpsertRequest(
            country_code=country_code,
        )


def test_billing_profile_contract_forbids_identity_and_policy_fields() -> None:
    with pytest.raises(ValidationError):
        BillingProfileUpsertRequest.model_validate(
            {
                "country_code": "TN",
                "user_id": str(uuid.uuid4()),
                "organization_id": str(uuid.uuid4()),
                "status": "active",
                "show_tunisia_payment_option": True,
            }
        )
