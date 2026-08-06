from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol

from processual_api.admin_marketplace.lemon_squeezy_inbox_lifecycle import (
    claim_lemon_squeezy_webhook,
    mark_lemon_squeezy_webhook_processed,
    mark_lemon_squeezy_webhook_rejected,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_gate import (
    LemonSqueezyReconciliationContext,
    classify_lemon_squeezy_reconciliation,
)
from processual_api.admin_marketplace.lemon_squeezy_reconciliation_persistence import (
    LemonSqueezyReconciliationDecisionRecord,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)


class LemonSqueezyReconciliationUnitOfWork(Protocol):
    lemon_squeezy_webhook_inbox: object
    lemon_squeezy_reconciliation_decisions: object

    async def __aenter__(self) -> "LemonSqueezyReconciliationUnitOfWork": ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...


ContextLoader = Callable[
    [LemonSqueezyReconciliationUnitOfWork, object],
    Awaitable[LemonSqueezyReconciliationContext],
]


def _aware_now(value: datetime | None) -> datetime:
    timestamp = value or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise LemonSqueezyWebhookError("decided_at must be timezone-aware.")
    return timestamp


def _stored_binding_matches(existing: object, inbox: object) -> bool:
    return (
        getattr(existing, "inbox_id", None) == getattr(inbox, "id", None)
        and getattr(existing, "event_identity_hash", None)
        == getattr(inbox, "event_identity_hash", None)
        and getattr(existing, "customer_ref", None) == getattr(inbox, "customer_ref", None)
        and getattr(existing, "order_ref", None) == getattr(inbox, "order_ref", None)
        and getattr(existing, "offer_ref", None) == getattr(inbox, "offer_ref", None)
    )


def _context_binding_matches(
    context: LemonSqueezyReconciliationContext,
    inbox: object,
) -> bool:
    return (
        context.expected_customer_ref == getattr(inbox, "customer_ref", None)
        and context.expected_order_ref == getattr(inbox, "order_ref", None)
        and context.expected_offer_ref == getattr(inbox, "offer_ref", None)
    )


def _as_record(existing: object) -> LemonSqueezyReconciliationDecisionRecord:
    return LemonSqueezyReconciliationDecisionRecord(
        id=existing.id,
        inbox_id=existing.inbox_id,
        event_identity_hash=existing.event_identity_hash,
        customer_ref=existing.customer_ref,
        order_ref=existing.order_ref,
        offer_ref=existing.offer_ref,
        action=existing.action,
        reason_code=existing.reason_code,
        decided_at=existing.decided_at,
    )


def process_lemon_squeezy_reconciliation_factory(
    *,
    uow_factory: Callable[[], LemonSqueezyReconciliationUnitOfWork],
    context_loader: ContextLoader,
):
    async def process(
        *,
        inbox_id: uuid.UUID,
        decided_at: datetime | None = None,
    ) -> LemonSqueezyReconciliationDecisionRecord:
        timestamp = _aware_now(decided_at)

        async with uow_factory() as uow:
            inbox = await uow.lemon_squeezy_webhook_inbox.get_by_id(
                inbox_id,
                for_update=True,
            )
            if inbox is None:
                raise LemonSqueezyWebhookError("webhook inbox entry was not found.")

            existing = await uow.lemon_squeezy_reconciliation_decisions.get_by_inbox_id(
                inbox_id,
                for_update=True,
            )
            if existing is not None:
                if not _stored_binding_matches(existing, inbox):
                    raise LemonSqueezyWebhookError(
                        "stored reconciliation decision conflicts with inbox binding."
                    )
                return _as_record(existing)

            claim_lemon_squeezy_webhook(inbox, claimed_at=timestamp)
            context = await context_loader(uow, inbox)
            if not _context_binding_matches(context, inbox):
                raise LemonSqueezyWebhookError(
                    "reconciliation context conflicts with inbox binding."
                )
            decision = classify_lemon_squeezy_reconciliation(
                entry=inbox,
                context=context,
            )

            record = LemonSqueezyReconciliationDecisionRecord(
                id=uuid.uuid4(),
                inbox_id=inbox.id,
                event_identity_hash=inbox.event_identity_hash,
                customer_ref=inbox.customer_ref,
                order_ref=inbox.order_ref,
                offer_ref=inbox.offer_ref,
                action=decision.action,
                reason_code=decision.reason_code,
                decided_at=timestamp,
            )
            uow.lemon_squeezy_reconciliation_decisions.add(record)

            if decision.action == "requires_review":
                mark_lemon_squeezy_webhook_rejected(
                    inbox,
                    error_code=decision.reason_code,
                    rejected_at=timestamp,
                )
            else:
                mark_lemon_squeezy_webhook_processed(
                    inbox,
                    processed_at=timestamp,
                )

            await uow.commit()
            return record

    return process
