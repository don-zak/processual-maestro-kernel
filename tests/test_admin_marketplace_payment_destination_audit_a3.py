from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
)

PAYMENT_DESTINATION_ACTIONS = {
    "payment_destination_created",
    "payment_destination_validated",
    "payment_destination_activated",
    "payment_destination_deactivated",
    "payment_destination_default_set",
}


def test_payment_destination_audit_vocabulary_is_explicit() -> None:
    assert {
        CommercialAuditAction.PAYMENT_DESTINATION_CREATED.value,
        CommercialAuditAction.PAYMENT_DESTINATION_VALIDATED.value,
        CommercialAuditAction.PAYMENT_DESTINATION_ACTIVATED.value,
        CommercialAuditAction.PAYMENT_DESTINATION_DEACTIVATED.value,
        CommercialAuditAction.PAYMENT_DESTINATION_DEFAULT_SET.value,
    } == PAYMENT_DESTINATION_ACTIONS

    assert (
        CommercialResourceType.PAYMENT_DESTINATION.value
        == "payment_destination"
    )


@pytest.mark.parametrize(
    "action",
    [
        CommercialAuditAction.PAYMENT_DESTINATION_CREATED,
        CommercialAuditAction.PAYMENT_DESTINATION_VALIDATED,
        CommercialAuditAction.PAYMENT_DESTINATION_ACTIVATED,
        CommercialAuditAction.PAYMENT_DESTINATION_DEACTIVATED,
        CommercialAuditAction.PAYMENT_DESTINATION_DEFAULT_SET,
    ],
)
def test_payment_destination_audit_records_are_accepted(action) -> None:
    record = CommercialAuditRecord(
        event_id="event_001",
        occurred_at=datetime.now(UTC),
        actor_user_id="admin_001",
        actor_session_id="session_001",
        platform_authority="platform_admin",
        action=action,
        resource_type=CommercialResourceType.PAYMENT_DESTINATION,
        resource_id="destination_001",
        outcome=CommercialAuditOutcome.ALLOWED,
        reason_code="payment_destination_transition_allowed",
        correlation_id="correlation_001",
        previous_state_digest="a" * 64,
        new_state_digest="b" * 64,
        metadata={
            "sales_channel": "maestro_direct",
            "country_code": "TN",
            "currency": "TND",
        },
    )

    assert record.action is action
    assert (
        record.resource_type
        is CommercialResourceType.PAYMENT_DESTINATION
    )


def test_database_checks_include_payment_destination_vocabulary() -> None:
    check_sql = {
        str(constraint.sqltext)
        for constraint in AdminMarketAuditRecord.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    combined = "\n".join(check_sql)

    assert PAYMENT_DESTINATION_ACTIONS <= {
        action
        for action in PAYMENT_DESTINATION_ACTIONS
        if action in combined
    }
    assert "payment_destination" in combined


def test_postgresql_audit_table_compiles_with_extended_vocabulary() -> None:
    sql = str(
        CreateTable(AdminMarketAuditRecord.__table__).compile(
            dialect=postgresql.dialect()
        )
    )

    for action in PAYMENT_DESTINATION_ACTIONS:
        assert action in sql

    assert "'payment_destination'" in sql
