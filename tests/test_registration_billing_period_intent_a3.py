from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import CheckConstraint

from processual_api.auth.models import AuthRegistrationPlanIntent
from processual_api.auth.registration_contracts import (
    IndividualRegistrationRequestContract,
)


def _payload(**overrides):
    payload = {
        "email": "person@example.test",
        "full_name": "Example Person",
        "password": "correct horse battery staple",
        "accepted_terms_version": "2026-08",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("billing_period", ["monthly", "annual"])
def test_registration_contract_accepts_direct_plan_billing_period(
    billing_period,
):
    contract = IndividualRegistrationRequestContract(
        **_payload(
            selected_plan_id="starter",
            billing_period=billing_period,
        )
    )

    assert contract.selected_plan_id == "starter"
    assert contract.billing_period == billing_period


def test_registration_contract_preserves_legacy_registration_without_plan():
    contract = IndividualRegistrationRequestContract(**_payload())

    assert contract.selected_plan_id is None
    assert contract.billing_period is None


@pytest.mark.parametrize(
    "values",
    [
        {"selected_plan_id": "starter"},
        {"billing_period": "monthly"},
        {
            "selected_plan_id": "starter",
            "billing_period": "weekly",
        },
    ],
)
def test_registration_contract_rejects_invalid_plan_billing_pair(values):
    with pytest.raises(ValidationError):
        IndividualRegistrationRequestContract(**_payload(**values))


def test_registration_plan_intent_model_contains_billing_period():
    table = AuthRegistrationPlanIntent.__table__

    assert "billing_period" in table.columns
    assert table.columns.billing_period.nullable is True
    assert table.columns.billing_period.type.length == 16

    check_sql = {
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert any(
        "billing_period" in expression
        and "monthly" in expression
        and "annual" in expression
        for expression in check_sql
    )


def test_billing_period_migration_is_reversible_and_preserves_legacy_rows():
    path = Path(
        "alembic/versions/"
        "20260804_0016_registration_intent_billing_period.py"
    )
    source = path.read_text(encoding="utf-8")

    assert 'revision: str = "20260804_0016"' in source
    assert 'down_revision: str | None = "20260803_0015"' in source
    assert 'sa.Column("billing_period", sa.String(length=16), nullable=True)' in source
    assert "batch_op.create_check_constraint(" in source
    assert "batch_op.drop_constraint(" in source
    assert 'batch_op.drop_column("billing_period")' in source
    assert "server_default" not in source
