from sqlalchemy import CheckConstraint, UniqueConstraint

from processual_api.auth.models import AuthDeliveryOutbox


def test_delivery_outbox_supports_exactly_one_authority() -> None:
    table = AuthDeliveryOutbox.__table__

    assert table.c.action_token_id.nullable is True
    assert table.c.account_recovery_request_id.nullable is True

    checks = {str(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, CheckConstraint)}

    combined = " ".join(checks)

    assert "action_token_id IS NOT NULL" in combined
    assert "account_recovery_request_id IS NULL" in combined
    assert "action_token_id IS NULL" in combined
    assert "account_recovery_request_id IS NOT NULL" in combined
    assert "account_recovery_verification" in combined


def test_each_delivery_authority_is_unique() -> None:
    table = AuthDeliveryOutbox.__table__

    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("action_token_id",) in unique_columns
    assert ("account_recovery_request_id",) in unique_columns
