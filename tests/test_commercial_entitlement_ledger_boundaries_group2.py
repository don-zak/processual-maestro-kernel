from datetime import UTC, datetime
from uuid import UUID

import pytest

from processual_api.billing.commercial_entitlement_ledger_boundaries import (
    ENTITLEMENT_LEDGER_BOUNDARIES_ENFORCEMENT_ENABLED,
    LedgerBoundaryViolationError,
    entitlement_ledger_boundaries_review_payload,
    validate_ledger_sequence,
)
from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementLedgerEntry,
    LedgerEntryType,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
SUBSCRIPTION_ID = UUID("22222222-2222-2222-2222-222222222222")
OTHER_SUBSCRIPTION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
RESERVATION_ID = UUID("33333333-3333-3333-3333-333333333333")
NOW = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)


def ledger_entry(
    *,
    entry_id: str,
    entry_type: LedgerEntryType,
    units: int,
    idempotency_key: str,
    source_reference: str,
    tenant_id: UUID = TENANT_ID,
    subscription_id: UUID = SUBSCRIPTION_ID,
    reservation_id: UUID | None = None,
    related_entry_id: UUID | None = None,
    adjustment_units: int | None = None,
    reason: str | None = None,
) -> EntitlementLedgerEntry:
    return EntitlementLedgerEntry(
        entry_id=UUID(entry_id),
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        entry_type=entry_type,
        units=units,
        idempotency_key=idempotency_key,
        occurred_at=NOW,
        source_reference=source_reference,
        reservation_id=reservation_id,
        related_entry_id=related_entry_id,
        adjustment_units=adjustment_units,
        reason=reason,
    )


def reserve(
    *,
    units: int = 5_000,
    tenant_id: UUID = TENANT_ID,
    subscription_id: UUID = SUBSCRIPTION_ID,
) -> EntitlementLedgerEntry:
    return ledger_entry(
        entry_id="44444444-4444-4444-4444-444444444444",
        entry_type=LedgerEntryType.USAGE_RESERVE,
        units=units,
        idempotency_key="reserve:job-1",
        source_reference="usage-job:job-1",
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        reservation_id=RESERVATION_ID,
    )


def commit(
    *,
    units: int = 4_000,
    tenant_id: UUID = TENANT_ID,
    subscription_id: UUID = SUBSCRIPTION_ID,
) -> EntitlementLedgerEntry:
    return ledger_entry(
        entry_id="55555555-5555-5555-5555-555555555555",
        entry_type=LedgerEntryType.USAGE_COMMIT,
        units=units,
        idempotency_key="commit:job-1",
        source_reference="usage-job:job-1",
        tenant_id=tenant_id,
        subscription_id=subscription_id,
        reservation_id=RESERVATION_ID,
    )


def release() -> EntitlementLedgerEntry:
    return ledger_entry(
        entry_id="66666666-6666-6666-6666-666666666666",
        entry_type=LedgerEntryType.USAGE_RELEASE,
        units=5_000,
        idempotency_key="release:job-1",
        source_reference="usage-job:job-1",
        reservation_id=RESERVATION_ID,
    )


def test_boundaries_remain_review_only() -> None:
    payload = entitlement_ledger_boundaries_review_payload()

    assert ENTITLEMENT_LEDGER_BOUNDARIES_ENFORCEMENT_ENABLED is False
    assert payload["status"] == "draft_review"
    assert payload["enforcement_enabled"] is False


def test_valid_reserve_and_commit_sequence() -> None:
    result = validate_ledger_sequence((reserve(), commit()))

    assert result.valid is True
    assert result.reservation_count == 1
    assert result.enforcement_enabled is False


def test_commit_without_reserve_is_rejected() -> None:
    with pytest.raises(
        LedgerBoundaryViolationError,
        match="exactly one reserve",
    ):
        validate_ledger_sequence((commit(),))


def test_release_without_reserve_is_rejected() -> None:
    with pytest.raises(
        LedgerBoundaryViolationError,
        match="exactly one reserve",
    ):
        validate_ledger_sequence((release(),))


def test_commit_and_release_are_mutually_exclusive() -> None:
    with pytest.raises(
        LedgerBoundaryViolationError,
        match="both committed and released",
    ):
        validate_ledger_sequence((reserve(), commit(), release()))


def test_duplicate_commit_is_rejected() -> None:
    second_commit = ledger_entry(
        entry_id="77777777-7777-7777-7777-777777777777",
        entry_type=LedgerEntryType.USAGE_COMMIT,
        units=4_000,
        idempotency_key="commit:job-1:retry",
        source_reference="usage-job:job-1",
        reservation_id=RESERVATION_ID,
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="committed more than once",
    ):
        validate_ledger_sequence((reserve(), commit(), second_commit))


def test_commit_must_not_exceed_reserved_units() -> None:
    with pytest.raises(
        LedgerBoundaryViolationError,
        match="must not exceed reserved units",
    ):
        validate_ledger_sequence((reserve(units=4_000), commit(units=5_000)))


def test_cross_tenant_commit_is_rejected() -> None:
    with pytest.raises(
        LedgerBoundaryViolationError,
        match="same tenant",
    ):
        validate_ledger_sequence(
            (
                reserve(),
                commit(tenant_id=OTHER_TENANT_ID),
            )
        )


def test_cross_subscription_commit_is_rejected() -> None:
    with pytest.raises(
        LedgerBoundaryViolationError,
        match="same subscription",
    ):
        validate_ledger_sequence(
            (
                reserve(),
                commit(subscription_id=OTHER_SUBSCRIPTION_ID),
            )
        )


def test_reversal_requires_commit() -> None:
    reversal = ledger_entry(
        entry_id="88888888-8888-8888-8888-888888888888",
        entry_type=LedgerEntryType.USAGE_REVERSAL,
        units=4_000,
        idempotency_key="reversal:job-1",
        source_reference="usage-job:job-1",
        reservation_id=RESERVATION_ID,
        related_entry_id=UUID("55555555-5555-5555-5555-555555555555"),
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="requires an earlier usage commit",
    ):
        validate_ledger_sequence((reserve(), reversal))


def test_reversal_must_reference_commit() -> None:
    reversal = ledger_entry(
        entry_id="88888888-8888-8888-8888-888888888888",
        entry_type=LedgerEntryType.USAGE_REVERSAL,
        units=4_000,
        idempotency_key="reversal:job-1",
        source_reference="usage-job:job-1",
        reservation_id=RESERVATION_ID,
        related_entry_id=UUID("99999999-9999-9999-9999-999999999999"),
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="must reference its usage commit",
    ):
        validate_ledger_sequence((reserve(), commit(), reversal))


def test_reversal_must_not_exceed_commit() -> None:
    committed = commit(units=3_000)
    reversal = ledger_entry(
        entry_id="88888888-8888-8888-8888-888888888888",
        entry_type=LedgerEntryType.USAGE_REVERSAL,
        units=4_000,
        idempotency_key="reversal:job-1",
        source_reference="usage-job:job-1",
        reservation_id=RESERVATION_ID,
        related_entry_id=committed.entry_id,
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="must not exceed committed units",
    ):
        validate_ledger_sequence((reserve(), committed, reversal))


def test_duplicate_monthly_grant_cycle_is_rejected() -> None:
    first = ledger_entry(
        entry_id="aaaaaaaa-1111-1111-1111-111111111111",
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07:first",
        source_reference="billing-cycle:2026-07",
    )
    second = ledger_entry(
        entry_id="aaaaaaaa-2222-2222-2222-222222222222",
        entry_type=LedgerEntryType.MONTHLY_GRANT,
        units=10_000,
        idempotency_key="monthly:2026-07:second",
        source_reference="billing-cycle:2026-07",
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="duplicate monthly grant",
    ):
        validate_ledger_sequence((first, second))


def test_top_up_requires_approved_grant_reference() -> None:
    top_up = ledger_entry(
        entry_id="bbbbbbbb-1111-1111-1111-111111111111",
        entry_type=LedgerEntryType.TOP_UP_GRANT,
        units=10_000,
        idempotency_key="top-up:order-1",
        source_reference="unverified-payment:order-1",
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="approved grant source reference",
    ):
        validate_ledger_sequence((top_up,))


def test_duplicate_top_up_source_is_rejected() -> None:
    first = ledger_entry(
        entry_id="bbbbbbbb-1111-1111-1111-111111111111",
        entry_type=LedgerEntryType.TOP_UP_GRANT,
        units=10_000,
        idempotency_key="top-up:order-1:first",
        source_reference="top-up-order:order-1",
    )
    second = ledger_entry(
        entry_id="bbbbbbbb-2222-2222-2222-222222222222",
        entry_type=LedgerEntryType.TOP_UP_GRANT,
        units=10_000,
        idempotency_key="top-up:order-1:second",
        source_reference="top-up-order:order-1",
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="duplicate top-up grant source",
    ):
        validate_ledger_sequence((first, second))


def test_admin_adjustment_requires_platform_admin_reference() -> None:
    adjustment = ledger_entry(
        entry_id="cccccccc-1111-1111-1111-111111111111",
        entry_type=LedgerEntryType.ADMIN_ADJUSTMENT,
        units=1,
        idempotency_key="admin-adjustment:1",
        source_reference="delegated-supervisor:1",
        adjustment_units=1_000,
        reason="approved correction",
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="platform-admin authority reference",
    ):
        validate_ledger_sequence((adjustment,))


def test_refund_reversal_must_not_exceed_grant() -> None:
    grant = ledger_entry(
        entry_id="dddddddd-1111-1111-1111-111111111111",
        entry_type=LedgerEntryType.TOP_UP_GRANT,
        units=5_000,
        idempotency_key="top-up:order-2",
        source_reference="top-up-order:order-2",
    )
    refund = ledger_entry(
        entry_id="dddddddd-2222-2222-2222-222222222222",
        entry_type=LedgerEntryType.REFUND_REVERSAL,
        units=6_000,
        idempotency_key="refund:order-2",
        source_reference="refund:order-2",
        related_entry_id=grant.entry_id,
    )

    with pytest.raises(
        LedgerBoundaryViolationError,
        match="must not exceed granted units",
    ):
        validate_ledger_sequence((grant, refund))
