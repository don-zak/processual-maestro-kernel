from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from processual_api.db.session import get_session_factory
from processual_api.services.api_key_store import _verify_stored_key
from processual_api.services.evaluation_grant_persistence import (
    SqlAlchemyEvaluationAuthorityRepository,
)


class DurableEvaluationApiKeyDenied(PermissionError):  # noqa: N818
    """A matching durable evaluation key exists but cannot receive authority."""


def _deny(reason: str) -> None:
    raise DurableEvaluationApiKeyDenied(reason)


async def verify_durable_evaluation_api_key(api_key: str) -> dict[str, Any] | None:
    if not api_key or not api_key.startswith("pmk_"):
        return None

    prefix = api_key[:12]
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyEvaluationAuthorityRepository(session)
        candidates = await repository.key_candidates_by_prefix(prefix, for_update=True)
        if not candidates:
            return None

        now = datetime.now(UTC)
        for key in candidates:
            if not _verify_stored_key(api_key, key.key_hash):
                continue

            if key.status != "enabled" or key.revoked_at is not None:
                _deny("durable_evaluation_key_revoked_or_disabled")
            if key.expires_at <= now:
                key.status = "expired"
                await session.commit()
                _deny("durable_evaluation_key_expired")

            grant = await repository.get_grant_by_id(key.grant_id, for_update=True)
            if grant is None:
                _deny("durable_evaluation_grant_missing")
            if grant.refresh_status(now=now) != "active":
                await session.commit()
                _deny("durable_evaluation_grant_inactive")
            if grant.client_ref != key.client_ref or grant.user_ref != key.user_ref:
                _deny("durable_evaluation_key_subject_mismatch")
            if set(key.scopes) != set(grant.allowed_scopes):
                _deny("durable_evaluation_key_scope_mismatch")
            if set(key.allowed_task_ids) != set(grant.allowed_task_ids):
                _deny("durable_evaluation_key_task_mismatch")

            key.last_used_at = now
            key.usage_count += 1
            await session.commit()
            return {
                "sub": key.user_ref,
                "user_id": key.user_ref,
                "client_id": key.client_ref,
                "role": "client",
                "auth_method": "api_key",
                "session_type": "evaluation_api_key",
                "api_key_id": key.key_ref,
                "api_key_authority_id": str(key.id),
                "api_key_prefix": key.key_prefix,
                "evaluation_grant_id": grant.grant_ref,
                "evaluation_grant_authority_id": str(grant.id),
                "entitlement_source": "admin_evaluation_grant",
                "subscription_required": False,
                "scopes": list(key.scopes),
                "allowed_task_ids": list(key.allowed_task_ids),
                "task_scope_ids": list(key.task_scope_ids),
                "task_authority_source": "integration_task_catalog",
                "quota_limit": int(grant.max_requests),
                "quota_used": int(grant.used_requests),
                "quota_source": "evaluation_usage_ledger",
                "production_allowed": False,
                "runtime_connector_approved": False,
            }

    return None


__all__ = [
    "DurableEvaluationApiKeyDenied",
    "verify_durable_evaluation_api_key",
]
