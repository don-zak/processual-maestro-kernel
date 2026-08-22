from __future__ import annotations

import uuid
from datetime import UTC, datetime

from processual_api.db.session import get_session_factory
from processual_api.services.evaluation_grant_persistence import (
    EvaluationUsageLedger,
    SqlAlchemyEvaluationAuthorityRepository,
)


class EvaluationUsageError(RuntimeError):
    """Durable evaluation usage authority rejected or could not record usage."""


async def record_evaluation_api_key_usage(
    *,
    current_user: dict,
    units: int,
    idempotency_key: str,
    task_id: str | None = None,
) -> EvaluationUsageLedger:
    if units <= 0:
        raise EvaluationUsageError("evaluation_usage_units_must_be_positive")
    if not idempotency_key or len(idempotency_key) > 128:
        raise EvaluationUsageError("evaluation_usage_idempotency_invalid")

    try:
        grant_id = uuid.UUID(str(current_user["evaluation_grant_authority_id"]))
        key_id = uuid.UUID(str(current_user["api_key_authority_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise EvaluationUsageError("evaluation_usage_identity_invalid") from exc

    normalized_task = str(task_id or "").strip().lower() or None
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyEvaluationAuthorityRepository(session)
        grant = await repository.get_grant_by_id(grant_id, for_update=True)
        key = await repository.get_key_by_id(key_id, for_update=True)
        if grant is None or key is None or key.grant_id != grant.id:
            raise EvaluationUsageError("evaluation_usage_authority_missing")

        existing = await repository.usage_by_idempotency(grant.id, idempotency_key)
        if existing is not None:
            return existing

        now = datetime.now(UTC)
        if grant.refresh_status(now=now) != "active":
            await session.commit()
            raise EvaluationUsageError("evaluation_grant_inactive")
        if key.status != "enabled" or key.revoked_at is not None or key.expires_at <= now:
            if key.expires_at <= now and key.status == "enabled":
                key.status = "expired"
                await session.commit()
            raise EvaluationUsageError("evaluation_key_inactive")
        if key.client_ref != grant.client_ref or key.user_ref != grant.user_ref:
            raise EvaluationUsageError("evaluation_usage_subject_mismatch")
        if normalized_task and normalized_task not in set(grant.allowed_task_ids):
            raise EvaluationUsageError("evaluation_task_not_allowed")

        requested_total = int(grant.used_requests) + int(units)
        if requested_total > int(grant.max_requests):
            grant.rejected_requests += 1
            await session.commit()
            raise EvaluationUsageError("evaluation_quota_limit_exceeded")

        usage = EvaluationUsageLedger(
            id=uuid.uuid4(),
            grant_id=grant.id,
            key_id=key.id,
            idempotency_key=idempotency_key,
            units=units,
            task_id=normalized_task,
        )
        grant.used_requests = requested_total
        repository.add(usage)
        await session.flush()
        await session.commit()
        return usage


__all__ = [
    "EvaluationUsageError",
    "record_evaluation_api_key_usage",
]
