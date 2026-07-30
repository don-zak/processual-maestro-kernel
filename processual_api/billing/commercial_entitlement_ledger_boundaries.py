"""Review-only sequence boundaries for the entitlement ledger.

This module validates relationships between immutable ledger entries. It does
not write entries, mutate balances, persist data, or enable runtime charging.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from processual_api.billing.commercial_entitlement_ledger_contracts import (
    EntitlementLedgerEntry,
    LedgerEntryType,
)

ENTITLEMENT_LEDGER_BOUNDARIES_VERSION: Final = "2026-07-group2-entitlement-ledger-boundaries-v1"
ENTITLEMENT_LEDGER_BOUNDARIES_STATUS: Final = "draft_review"
ENTITLEMENT_LEDGER_BOUNDARIES_ENFORCEMENT_ENABLED: Final = False


class LedgerBoundaryViolationError(ValueError):
    """Raised when immutable ledger entries violate a sequence boundary."""


@dataclass(frozen=True, slots=True)
class LedgerSequenceValidation:
    valid: bool
    entry_count: int
    reservation_count: int
    monthly_grant_count: int
    top_up_grant_count: int
    enforcement_enabled: bool = ENTITLEMENT_LEDGER_BOUNDARIES_ENFORCEMENT_ENABLED


def _require_same_commercial_scope(
    *,
    first: EntitlementLedgerEntry,
    second: EntitlementLedgerEntry,
) -> None:
    if first.tenant_id != second.tenant_id:
        raise LedgerBoundaryViolationError("related ledger entries must use the same tenant")

    if first.subscription_id != second.subscription_id:
        raise LedgerBoundaryViolationError("related ledger entries must use the same subscription")


def _validate_monthly_grants(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> int:
    seen_cycles: set[tuple[UUID, UUID, str]] = set()
    count = 0

    for entry in entries:
        if entry.entry_type is not LedgerEntryType.MONTHLY_GRANT:
            continue

        identity = (
            entry.tenant_id,
            entry.subscription_id,
            entry.source_reference,
        )

        if identity in seen_cycles:
            raise LedgerBoundaryViolationError("duplicate monthly grant for the same billing cycle")

        seen_cycles.add(identity)
        count += 1

    return count


def _validate_top_up_grants(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> int:
    seen_sources: set[tuple[UUID, UUID, str]] = set()
    count = 0

    for entry in entries:
        if entry.entry_type is not LedgerEntryType.TOP_UP_GRANT:
            continue

        identity = (
            entry.tenant_id,
            entry.subscription_id,
            entry.source_reference,
        )

        if identity in seen_sources:
            raise LedgerBoundaryViolationError("duplicate top-up grant source reference")

        if not entry.source_reference.startswith(("top-up-order:", "top-up-grant:")):
            raise LedgerBoundaryViolationError("top-up grant requires an approved grant source reference")

        seen_sources.add(identity)
        count += 1

    return count


def _validate_reservation_sequences(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> int:
    reservation_entries: dict[
        UUID,
        list[EntitlementLedgerEntry],
    ] = defaultdict(list)

    for entry in entries:
        if entry.reservation_id is not None:
            reservation_entries[entry.reservation_id].append(entry)

    for reservation_id, lifecycle in reservation_entries.items():
        reserves = [entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_RESERVE]
        commits = [entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_COMMIT]
        releases = [entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_RELEASE]
        reversals = [entry for entry in lifecycle if entry.entry_type is LedgerEntryType.USAGE_REVERSAL]

        if len(reserves) != 1:
            raise LedgerBoundaryViolationError("reservation lifecycle requires exactly one reserve entry")

        reserve = reserves[0]

        for related in commits + releases + reversals:
            _require_same_commercial_scope(
                first=reserve,
                second=related,
            )

        if len(commits) > 1:
            raise LedgerBoundaryViolationError("reservation must not be committed more than once")

        if len(releases) > 1:
            raise LedgerBoundaryViolationError("reservation must not be released more than once")

        if commits and releases:
            raise LedgerBoundaryViolationError("reservation must not be both committed and released")

        if reversals and not commits:
            raise LedgerBoundaryViolationError("usage reversal requires an earlier usage commit")

        if len(reversals) > 1:
            raise LedgerBoundaryViolationError("usage commit must not be reversed more than once")

        if commits:
            commit = commits[0]

            if commit.units > reserve.units:
                raise LedgerBoundaryViolationError("usage commit must not exceed reserved units")

            for reversal in reversals:
                if reversal.related_entry_id != commit.entry_id:
                    raise LedgerBoundaryViolationError("usage reversal must reference its usage commit")

                if reversal.units > commit.units:
                    raise LedgerBoundaryViolationError("usage reversal must not exceed committed units")

        if releases:
            release = releases[0]

            if release.units > reserve.units:
                raise LedgerBoundaryViolationError("usage release must not exceed reserved units")

    return len(reservation_entries)


def _validate_refund_reversals(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> None:
    entries_by_id = {entry.entry_id: entry for entry in entries}

    for entry in entries:
        if entry.entry_type is not LedgerEntryType.REFUND_REVERSAL:
            continue

        assert entry.related_entry_id is not None
        related = entries_by_id.get(entry.related_entry_id)

        if related is None:
            raise LedgerBoundaryViolationError("refund reversal requires its related grant entry")

        if related.entry_type not in {
            LedgerEntryType.MONTHLY_GRANT,
            LedgerEntryType.TOP_UP_GRANT,
        }:
            raise LedgerBoundaryViolationError("refund reversal may reference only a grant entry")

        _require_same_commercial_scope(
            first=related,
            second=entry,
        )

        if entry.units > related.units:
            raise LedgerBoundaryViolationError("refund reversal must not exceed granted units")


def _validate_admin_adjustments(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> None:
    for entry in entries:
        if entry.entry_type is not LedgerEntryType.ADMIN_ADJUSTMENT:
            continue

        if not entry.source_reference.startswith("platform-admin:"):
            raise LedgerBoundaryViolationError("admin adjustment requires platform-admin authority reference")


def validate_ledger_sequence(
    entries: tuple[EntitlementLedgerEntry, ...],
) -> LedgerSequenceValidation:
    """Validate immutable ledger relationships without writing state."""

    seen_entry_ids: set[UUID] = set()
    seen_idempotency_keys: set[str] = set()

    for entry in entries:
        if entry.entry_id in seen_entry_ids:
            raise LedgerBoundaryViolationError("duplicate ledger entry id")

        if entry.idempotency_key in seen_idempotency_keys:
            raise LedgerBoundaryViolationError("duplicate ledger idempotency key")

        seen_entry_ids.add(entry.entry_id)
        seen_idempotency_keys.add(entry.idempotency_key)

    monthly_grant_count = _validate_monthly_grants(entries)
    top_up_grant_count = _validate_top_up_grants(entries)
    reservation_count = _validate_reservation_sequences(entries)
    _validate_refund_reversals(entries)
    _validate_admin_adjustments(entries)

    return LedgerSequenceValidation(
        valid=True,
        entry_count=len(entries),
        reservation_count=reservation_count,
        monthly_grant_count=monthly_grant_count,
        top_up_grant_count=top_up_grant_count,
    )


def entitlement_ledger_boundaries_review_payload() -> dict[str, object]:
    return {
        "version": ENTITLEMENT_LEDGER_BOUNDARIES_VERSION,
        "status": ENTITLEMENT_LEDGER_BOUNDARIES_STATUS,
        "enforcement_enabled": (ENTITLEMENT_LEDGER_BOUNDARIES_ENFORCEMENT_ENABLED),
        "commit_requires_reserve": True,
        "release_requires_reserve": True,
        "commit_and_release_mutually_exclusive": True,
        "duplicate_commit_rejected": True,
        "cross_tenant_relationship_rejected": True,
        "cross_subscription_relationship_rejected": True,
        "excess_commit_rejected": True,
        "excess_reversal_rejected": True,
        "duplicate_monthly_grant_rejected": True,
        "duplicate_top_up_source_rejected": True,
        "admin_authority_reference_required": True,
    }


__all__ = [
    "ENTITLEMENT_LEDGER_BOUNDARIES_ENFORCEMENT_ENABLED",
    "ENTITLEMENT_LEDGER_BOUNDARIES_STATUS",
    "ENTITLEMENT_LEDGER_BOUNDARIES_VERSION",
    "LedgerBoundaryViolationError",
    "LedgerSequenceValidation",
    "entitlement_ledger_boundaries_review_payload",
    "validate_ledger_sequence",
]
