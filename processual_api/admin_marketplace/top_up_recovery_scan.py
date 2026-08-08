from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TopUpRecoveryCandidate:
    kind: str
    order_id: uuid.UUID
    reference: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class TopUpRecoveryScanResult:
    candidates: tuple[TopUpRecoveryCandidate, ...]

    @property
    def count(self) -> int:
        return len(self.candidates)


async def scan_top_up_recovery_candidates(
    *,
    unit_of_work_factory: Callable[[], object],
    limit: int = 100,
) -> TopUpRecoveryScanResult:
    bounded_limit = max(1, min(limit, 500))
    candidates: list[TopUpRecoveryCandidate] = []

    async with unit_of_work_factory() as uow:
        orders = await uow.top_up_orders.list_recovery_candidates(limit=bounded_limit)
        for order in orders:
            if order.checkout_creation_status == "uncertain":
                candidates.append(
                    TopUpRecoveryCandidate(
                        kind="checkout_recovery",
                        order_id=order.id,
                        reference=str(order.provider_variant_id or "unbound"),
                        reason_code="checkout_creation_uncertain",
                    )
                )
            if order.state == "payment_verified":
                candidates.append(
                    TopUpRecoveryCandidate(
                        kind="grant_recovery",
                        order_id=order.id,
                        reference=order.channel,
                        reason_code="verified_payment_without_grant",
                    )
                )

        remaining = max(0, bounded_limit - len(candidates))
        if remaining:
            reversals = await uow.subscription_top_up_reversals.list_manual_review(
                limit=remaining
            )
            candidates.extend(
                TopUpRecoveryCandidate(
                    kind="reversal_review",
                    order_id=reversal.order_id,
                    reference=reversal.provider_event_ref,
                    reason_code=reversal.reason_code,
                )
                for reversal in reversals
            )

    return TopUpRecoveryScanResult(candidates=tuple(candidates[:bounded_limit]))


__all__ = [
    "TopUpRecoveryCandidate",
    "TopUpRecoveryScanResult",
    "scan_top_up_recovery_candidates",
]
