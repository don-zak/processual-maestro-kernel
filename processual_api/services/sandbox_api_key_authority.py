from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from processual_api.admin_marketplace.subscription_runtime_persistence import (
    SqlAlchemySubscriptionRuntimeRepository,
)
from processual_api.db.session import get_session_factory
from processual_api.services.api_key_store import _verify_stored_key
from processual_api.services.sandbox_api_key_persistence import (
    SqlAlchemySandboxApiKeyRepository,
)


async def verify_durable_sandbox_api_key(api_key: str) -> dict[str, Any] | None:
    """Verify a sandbox API key against durable PostgreSQL authority.

    Database/runtime failures are intentionally allowed to propagate so the
    authentication boundary can fail closed rather than silently granting a
    legacy identity.
    """

    if not api_key or not api_key.startswith("pmk_"):
        return None

    prefix = api_key[:12]
    session_factory = get_session_factory()
    async with session_factory() as session:
        keys = SqlAlchemySandboxApiKeyRepository(session)
        runtimes = SqlAlchemySubscriptionRuntimeRepository(session)
        candidates = await keys.candidates_by_prefix(prefix, for_update=True)
        if not candidates:
            return None

        now = datetime.now(UTC)
        for key in candidates:
            if key.environment != "sandbox":
                continue
            if key.status != "enabled" or key.revoked_at is not None:
                continue
            if key.expires_at <= now:
                key.status = "expired"
                await session.commit()
                continue
            if not _verify_stored_key(api_key, key.key_hash):
                continue

            runtime = await runtimes.get_by_subscription_id(
                key.subscription_id,
                for_update=True,
            )
            if runtime is None:
                return None
            if runtime.customer_ref != key.client_ref:
                return None
            if runtime.access_stage not in {"active", "grace"}:
                return None

            key.mark_used(at=now)
            await session.commit()
            return {
                "sub": key.owner_user_ref,
                "user_id": key.owner_user_ref,
                "client_id": key.client_ref,
                "role": "client",
                "auth_method": "api_key",
                "session_type": "sandbox_api_key",
                "api_key_id": str(key.id),
                "api_key_prefix": key.key_prefix,
                "subscription_id": str(key.subscription_id),
                "plan_id": key.plan_id,
                "operational_profile_id": key.operational_profile_id,
                "environment": "sandbox",
                "scopes": key.scopes,
                "production_allowed": False,
                "runtime_connector_approved": False,
            }

    return None
