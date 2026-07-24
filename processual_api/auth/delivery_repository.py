from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from processual_api.auth.delivery_contracts import (
    DeliveryClaim,
    DeliveryOperationalMetrics,
    DeliveryRedriveResult,
)
from processual_api.auth.models import (
    AuthAccountRecoveryRequest,
    AuthActionToken,
    AuthDeliveryOutbox,
    IdentityUser,
    IdentityUserEmailAddress,
)


class SqlAlchemyDeliveryRepository:
    def __init__(
        self,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def claim_batch(
        self,
        *,
        now: datetime,
        lease_timeout: timedelta,
        batch_size: int,
    ) -> tuple[DeliveryClaim, ...]:
        stale_before = now - lease_timeout

        pending_recovery_email = aliased(IdentityUserEmailAddress)
        verified_recovery_email = aliased(IdentityUserEmailAddress)

        async with self._session_factory() as session:
            async with session.begin():
                statement = (
                    select(
                        AuthDeliveryOutbox,
                        IdentityUser,
                        AuthActionToken,
                        AuthAccountRecoveryRequest,
                        pending_recovery_email,
                        verified_recovery_email,
                    )
                    .join(
                        IdentityUser,
                        IdentityUser.id == AuthDeliveryOutbox.user_id,
                    )
                    .outerjoin(
                        AuthActionToken,
                        AuthActionToken.id == AuthDeliveryOutbox.action_token_id,
                    )
                    .outerjoin(
                        AuthAccountRecoveryRequest,
                        AuthAccountRecoveryRequest.id == (AuthDeliveryOutbox.account_recovery_request_id),
                    )
                    .outerjoin(
                        pending_recovery_email,
                        and_(
                            pending_recovery_email.user_id == AuthDeliveryOutbox.user_id,
                            pending_recovery_email.purpose == "recovery",
                            pending_recovery_email.status == "pending",
                            pending_recovery_email.revoked_at.is_(None),
                        ),
                    )
                    .outerjoin(
                        verified_recovery_email,
                        and_(
                            verified_recovery_email.user_id == AuthDeliveryOutbox.user_id,
                            verified_recovery_email.purpose == "recovery",
                            verified_recovery_email.status == "verified",
                            verified_recovery_email.verified_at.is_not(None),
                            verified_recovery_email.revoked_at.is_(None),
                        ),
                    )
                    .where(
                        AuthDeliveryOutbox.delivered_at.is_(None),
                        AuthDeliveryOutbox.dead_lettered_at.is_(None),
                        AuthDeliveryOutbox.available_at <= now,
                        or_(
                            AuthDeliveryOutbox.claimed_at.is_(None),
                            AuthDeliveryOutbox.claimed_at <= stale_before,
                        ),
                    )
                    .order_by(
                        AuthDeliveryOutbox.available_at,
                        AuthDeliveryOutbox.created_at,
                    )
                    .limit(batch_size)
                    .with_for_update(
                        of=AuthDeliveryOutbox,
                        skip_locked=True,
                    )
                )

                rows = (await session.execute(statement)).all()

                claims: list[DeliveryClaim] = []

                for (
                    outbox,
                    user,
                    action_token,
                    account_recovery_request,
                    pending_recovery_address,
                    verified_recovery_address,
                ) in rows:
                    claim_id = uuid.uuid4()
                    outbox.claim_id = claim_id
                    outbox.claimed_at = now
                    outbox.attempt_count += 1

                    if outbox.event_type == "verify_email":
                        recipient_email = user.email_normalized
                    elif outbox.event_type == "verify_recovery_email" and pending_recovery_address is not None:
                        recipient_email = pending_recovery_address.email_normalized
                    elif outbox.event_type == "account_recovery_verification" and verified_recovery_address is not None:
                        recipient_email = verified_recovery_address.email_normalized
                    else:
                        recipient_email = None

                    claims.append(
                        DeliveryClaim(
                            outbox_id=outbox.id,
                            user_id=outbox.user_id,
                            action_token_id=(outbox.action_token_id),
                            claim_id=claim_id,
                            recipient_email=recipient_email,
                            user_status=user.status,
                            event_type=outbox.event_type,
                            payload_ciphertext=bytes(outbox.payload_ciphertext),
                            payload_key_version=(outbox.payload_key_version),
                            action_token_expires_at=(action_token.expires_at if action_token is not None else None),
                            action_token_consumed_at=(action_token.consumed_at if action_token is not None else None),
                            action_token_invalidated_at=(
                                action_token.invalidated_at if action_token is not None else None
                            ),
                            attempt_count=(outbox.attempt_count),
                            account_recovery_request_id=(outbox.account_recovery_request_id),
                            account_recovery_expires_at=(
                                account_recovery_request.expires_at if (account_recovery_request is not None) else None
                            ),
                            account_recovery_state=(
                                account_recovery_request.state if (account_recovery_request is not None) else None
                            ),
                            account_recovery_revoked_at=(
                                account_recovery_request.revoked_at if (account_recovery_request is not None) else None
                            ),
                        )
                    )

            return tuple(claims)

    async def mark_delivered(
        self,
        *,
        outbox_id: uuid.UUID,
        claim_id: uuid.UUID,
        delivered_at: datetime,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    update(AuthDeliveryOutbox)
                    .where(
                        AuthDeliveryOutbox.id == outbox_id,
                        AuthDeliveryOutbox.claim_id == claim_id,
                        AuthDeliveryOutbox.delivered_at.is_(None),
                        AuthDeliveryOutbox.dead_lettered_at.is_(None),
                    )
                    .values(
                        delivered_at=delivered_at,
                        claim_id=None,
                        claimed_at=None,
                        last_error_code=None,
                    )
                )

            return result.rowcount == 1

    async def mark_failed(
        self,
        *,
        outbox_id: uuid.UUID,
        claim_id: uuid.UUID,
        available_at: datetime,
        error_code: str,
        dead_lettered_at: datetime | None,
    ) -> bool:
        async with self._session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    update(AuthDeliveryOutbox)
                    .where(
                        AuthDeliveryOutbox.id == outbox_id,
                        AuthDeliveryOutbox.claim_id == claim_id,
                        AuthDeliveryOutbox.delivered_at.is_(None),
                        AuthDeliveryOutbox.dead_lettered_at.is_(None),
                    )
                    .values(
                        available_at=available_at,
                        claim_id=None,
                        claimed_at=None,
                        last_error_code=error_code,
                        dead_lettered_at=dead_lettered_at,
                    )
                )

            return result.rowcount == 1

    async def redrive_dead_letter(
        self,
        *,
        outbox_id: uuid.UUID,
        available_at: datetime,
    ) -> DeliveryRedriveResult | None:
        if available_at.tzinfo is None:
            raise ValueError(
                "Delivery redrive availability must be timezone-aware."
            )

        async with self._session_factory() as session:
            async with session.begin():
                statement = (
                    update(AuthDeliveryOutbox)
                    .where(
                        AuthDeliveryOutbox.id == outbox_id,
                        AuthDeliveryOutbox.delivered_at.is_(None),
                        AuthDeliveryOutbox.dead_lettered_at.is_not(None),
                        AuthDeliveryOutbox.claim_id.is_(None),
                        AuthDeliveryOutbox.claimed_at.is_(None),
                    )
                    .values(
                        available_at=available_at,
                        dead_lettered_at=None,
                        claim_id=None,
                        claimed_at=None,
                        last_error_code=None,
                    )
                    .returning(
                        AuthDeliveryOutbox.id,
                        AuthDeliveryOutbox.available_at,
                        AuthDeliveryOutbox.attempt_count,
                    )
                )
                row = (await session.execute(statement)).one_or_none()

        if row is None:
            return None

        return DeliveryRedriveResult(
            outbox_id=row.id,
            available_at=row.available_at,
            preserved_attempt_count=row.attempt_count,
        )

    async def operational_metrics(
        self,
        *,
        now: datetime,
    ) -> DeliveryOperationalMetrics:
        if now.tzinfo is None:
            raise ValueError(
                "Delivery metrics clock must be timezone-aware."
            )

        pending_condition = and_(
            AuthDeliveryOutbox.delivered_at.is_(None),
            AuthDeliveryOutbox.dead_lettered_at.is_(None),
            AuthDeliveryOutbox.claimed_at.is_(None),
            AuthDeliveryOutbox.available_at <= now,
        )
        retry_scheduled_condition = and_(
            AuthDeliveryOutbox.delivered_at.is_(None),
            AuthDeliveryOutbox.dead_lettered_at.is_(None),
            AuthDeliveryOutbox.claimed_at.is_(None),
            AuthDeliveryOutbox.available_at > now,
        )
        leased_condition = and_(
            AuthDeliveryOutbox.delivered_at.is_(None),
            AuthDeliveryOutbox.dead_lettered_at.is_(None),
            AuthDeliveryOutbox.claimed_at.is_not(None),
        )
        dead_letter_condition = (
            AuthDeliveryOutbox.dead_lettered_at.is_not(None)
        )
        delivered_condition = (
            AuthDeliveryOutbox.delivered_at.is_not(None)
        )

        statement = select(
            func.count(
                case((pending_condition, 1))
            ).label("pending_count"),
            func.count(
                case((retry_scheduled_condition, 1))
            ).label("retry_scheduled_count"),
            func.count(
                case((leased_condition, 1))
            ).label("leased_count"),
            func.count(
                case((dead_letter_condition, 1))
            ).label("dead_letter_count"),
            func.count(
                case((delivered_condition, 1))
            ).label("delivered_count"),
            func.min(
                case(
                    (
                        pending_condition,
                        AuthDeliveryOutbox.created_at,
                    )
                )
            ).label("oldest_pending_created_at"),
        )

        async with self._session_factory() as session:
            row = (await session.execute(statement)).one()

        oldest_pending_age_seconds: int | None = None
        if row.oldest_pending_created_at is not None:
            age_seconds = int(
                (
                    now - row.oldest_pending_created_at
                ).total_seconds()
            )
            oldest_pending_age_seconds = max(0, age_seconds)

        return DeliveryOperationalMetrics(
            pending_count=int(row.pending_count or 0),
            retry_scheduled_count=int(
                row.retry_scheduled_count or 0
            ),
            leased_count=int(row.leased_count or 0),
            dead_letter_count=int(
                row.dead_letter_count or 0
            ),
            delivered_count=int(row.delivered_count or 0),
            oldest_pending_age_seconds=(
                oldest_pending_age_seconds
            ),
        )


__all__ = ["SqlAlchemyDeliveryRepository"]
