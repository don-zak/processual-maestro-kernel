from datetime import UTC, datetime
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    ENTITLEMENT_LEDGER_ENABLED,
    ENTITLEMENT_LEDGER_PERSISTENCE_ENABLED,
    EntitlementBalanceSnapshot,
    EntitlementLedgerEntry,
    LedgerDirection,
    LedgerEntryType,
    calculate_balance_from_entries,
    decide_usage_reservation,
    entitlement_ledger_review_payload,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBSCRIPTION_ID = UUID("22222222-2222-2222-2222-222222222222")
ENTRY_ID = UUID("33333333-3333-3333-3333-333333333333")
RESERVATION_ID = UUID("44444444-4444-4444-4444-444444444444")
RELATED_ENTRY_ID = UUID("55555555-5555-5555-5555-555555555555")
NOW = datetime(2026, 7, 30, 8, 30, tzinfo=UTC)


def entry(
    *,
    entry_id: UUID = ENTRY_ID,
    entry_type: LedgerEntryType,
    units: int,
    idempotency_key: str,
    reservation_id: UUID | None = None,
    related_entry_id: UUID | None = None,
    adjustment_units: int | None = None,
    reason: str | None = None,
) -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=entry_id,
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        entry_type=entry_type,
        units=units,
        idempotency_key=idempotency_key,
        occurred_at=NOW,
        source_reference="test://ledger",
        reservation_id=reservation_id,
        related_entry_id=related_entry_id,
        adjustment_units=adjustment_units,
        reason=reason,
    )


def test_ledger_remains_review_only() -> None:
    payload = entitlement_ledger_review_payload()

    assert ENTITLEMENT_LEDGER_ENABLED is False
    assert ENTITLEMENT_LEDGER_PERSISTENCE_ENABLED is False
    assert payload["status"] == "draft_review"
    assert payload["enabled"] is False
    assert payload["persistence_enabled"] is False


def test_monthly_and_top_up_grants_credit_balance() -> None:
    monthly = entry(
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07",
    )
    top_up = entry(
        entry_id=RELATED_ENTRY_ID,
        entry_type=LedgerEntryType.TOP_UP_GRANT,
        units=5_000,
        idempotency_key="top-up:order-1",
    )

    assert monthly.direction is LedgerDirection.CREDIT
    assert top_up.direction is LedgerDirection.CREDIT
    assert calculate_balance_from_entries((monthly, top_up)) == 15_000


def test_reservation_does_not_reduce_balance_before_commit() -> None:
    grant = entry(
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07",
    )
    reservation = entry(
        entry_id=RELATED_ENTRY_ID,
        entry_type=LedgerEntryType.USAGE_RESERVE,
        units=2_000,
        idempotency_key="reserve:job-1",
        reservation_id=RESERVATION_ID,
    )

    assert reservation.signed_units == 0
    assert calculate_balance_from_entries((grant, reservation)) == 10_000


def test_commit_debits_only_after_reservation() -> None:
    grant = entry(
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07",
    )
    reservation = entry(
        entry_id=RELATED_ENTRY_ID,
        entry_type=LedgerEntryType.USAGE_RESERVE,
        units=2_000,
        idempotency_key="reserve:job-1",
        reservation_id=RESERVATION_ID,
    )
    commit = entry(
        entry_id=UUID("66666666-6666-6666-6666-666666666666"),
        entry_type=LedgerEntryType.USAGE_COMMIT,
        units=2_000,
        idempotency_key="commit:job-1",
        reservation_id=RESERVATION_ID,
    )

    assert calculate_balance_from_entries((grant, reservation, commit)) == 8_000


def test_release_does_not_charge_failed_or_cancelled_work() -> None:
    grant = entry(
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07",
    )
    reservation = entry(
        entry_id=RELATED_ENTRY_ID,
        entry_type=LedgerEntryType.USAGE_RESERVE,
        units=2_000,
        idempotency_key="reserve:job-1",
        reservation_id=RESERVATION_ID,
    )
    release = entry(
        entry_id=UUID("77777777-7777-7777-7777-777777777777"),
        entry_type=LedgerEntryType.USAGE_RELEASE,
        units=2_000,
        idempotency_key="release:job-1",
        reservation_id=RESERVATION_ID,
    )

    assert calculate_balance_from_entries((grant, reservation, release)) == 10_000


def test_duplicate_idempotency_key_is_rejected() -> None:
    first = entry(
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:duplicate",
    )
    second = entry(
        entry_id=RELATED_ENTRY_ID,
        entry_type=LedgerEntryType.TOP_UP_GRANT,
        units=5_000,
        idempotency_key="monthly:duplicate",
    )

    with pytest.raises(
        ValueError,
        match="duplicate ledger idempotency key",
    ):
        calculate_balance_from_entries((first, second))


def test_negative_balance_is_rejected_by_default() -> None:
    commit = entry(
        entry_type=LedgerEntryType.USAGE_COMMIT,
        units=1_000,
        idempotency_key="commit:without-balance",
        reservation_id=RESERVATION_ID,
    )

    with pytest.raises(
        ValueError,
        match="negative balance",
    ):
        calculate_balance_from_entries((commit,))


def test_reservation_decision_uses_owned_balance() -> None:
    snapshot = EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=5_000,
        reserved_units=0,
        committed_units=0,
        calculated_at=NOW,
    )

    decision = decide_usage_reservation(
        snapshot=snapshot,
        reservation_id=RESERVATION_ID,
        requested_units=3_000,
    )

    assert decision.approved is True
    assert decision.ledger_write_enabled is False


def test_reservation_can_use_contractual_enterprise_overage() -> None:
    snapshot = EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=1_000,
        reserved_units=0,
        committed_units=0,
        calculated_at=NOW,
    )

    decision = decide_usage_reservation(
        snapshot=snapshot,
        reservation_id=RESERVATION_ID,
        requested_units=3_000,
        contracted_overage_units=2_000,
    )

    assert decision.approved is True


def test_reservation_rejects_insufficient_balance() -> None:
    snapshot = EntitlementBalanceSnapshot(
        tenant_id=TENANT_ID,
        subscription_id=SUBSCRIPTION_ID,
        available_units=1_000,
        reserved_units=0,
        committed_units=0,
        calculated_at=NOW,
    )

    decision = decide_usage_reservation(
        snapshot=snapshot,
        reservation_id=RESERVATION_ID,
        requested_units=3_000,
    )

    assert decision.approved is False


def test_usage_lifecycle_entries_require_reservation_id() -> None:
    with pytest.raises(
        ValueError,
        match="require reservation_id",
    ):
        entry(
            entry_type=LedgerEntryType.USAGE_COMMIT,
            units=1_000,
            idempotency_key="commit:no-reservation",
        )


def test_admin_adjustment_requires_reason() -> None:
    with pytest.raises(
        ValueError,
        match="requires an audit reason",
    ):
        entry(
            entry_type=LedgerEntryType.ADMIN_ADJUSTMENT,
            units=1,
            idempotency_key="admin-adjustment:1",
            adjustment_units=1_000,
        )


def test_reversal_requires_related_entry() -> None:
    with pytest.raises(
        ValueError,
        match="require related_entry_id",
    ):
        entry(
            entry_type=LedgerEntryType.USAGE_REVERSAL,
            units=1_000,
            idempotency_key="reversal:job-1",
            reservation_id=RESERVATION_ID,
        )
