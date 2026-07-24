from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from processual_api.auth.delivery_contracts import DeliveryClaim
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


__all__ = ["SqlAlchemyDeliveryRepository"]
