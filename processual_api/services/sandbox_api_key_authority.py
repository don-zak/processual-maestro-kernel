from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from processual_api.db.session import get_session_factory
from processual_api.services.api_key_store import _verify_stored_key
from processual_api.services.sandbox_api_key_persistence import (
    SqlAlchemySandboxApiKeyRepository,
)

# Kept as a module-level injection seam for focused authority tests. The real
# repository is loaded lazily to avoid importing Admin Marketplace routers while
# auth.security is still being initialized.
SqlAlchemySubscriptionRuntimeRepository: Any = None


class DurableSandboxApiKeyDenied(PermissionError):  # noqa: N818
    """A matching durable sandbox key exists but cannot receive authority."""


def _deny(reason: str) -> None:
    raise DurableSandboxApiKeyDenied(reason)


def _runtime_repository_class():
    global SqlAlchemySubscriptionRuntimeRepository
    if SqlAlchemySubscriptionRuntimeRepository is None:
        from processual_api.admin_marketplace.subscription_runtime_persistence import (
            SqlAlchemySubscriptionRuntimeRepository as RuntimeRepositoryClass,
        )

        SqlAlchemySubscriptionRuntimeRepository = RuntimeRepositoryClass
    return SqlAlchemySubscriptionRuntimeRepository


async def verify_durable_sandbox_api_key(api_key: str) -> dict[str, Any] | None:
    """Verify a sandbox API key against durable PostgreSQL authority.

    ``None`` means no durable key matched the presented secret and therefore a
    caller may evaluate an explicitly supported legacy source. A matching
    durable key that is revoked, expired, malformed, or bound to an unavailable
    subscription raises ``DurableSandboxApiKeyDenied`` so it can never fall
    through to weaker legacy authority.

    Database/runtime failures intentionally propagate. The HTTP authentication
    boundary must convert those failures to service-unavailable and fail closed.
    """

    if not api_key or not api_key.startswith("pmk_"):
        return None

    prefix = api_key[:12]
    session_factory = get_session_factory()
    async with session_factory() as session:
        keys = SqlAlchemySandboxApiKeyRepository(session)
        runtimes = _runtime_repository_class()(session)
        candidates = await keys.candidates_by_prefix(prefix, for_update=True)
        if not candidates:
            return None

        now = datetime.now(UTC)
        for key in candidates:
            if not _verify_stored_key(api_key, key.key_hash):
                continue

            if key.environment != "sandbox":
                _deny("durable_sandbox_key_environment_invalid")
            if key.status != "enabled" or key.revoked_at is not None:
                _deny("durable_sandbox_key_revoked_or_disabled")
            if key.expires_at <= now:
                key.status = "expired"
                await session.commit()
                _deny("durable_sandbox_key_expired")

            runtime = await runtimes.get_by_subscription_id(
                key.subscription_id,
                for_update=True,
            )
            if runtime is None:
                _deny("durable_sandbox_subscription_runtime_missing")
            if runtime.customer_ref != key.client_ref:
                _deny("durable_sandbox_subscription_customer_mismatch")
            if runtime.access_stage not in {"active", "grace"}:
                _deny("durable_sandbox_subscription_not_active")

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


__all__ = [
    "DurableSandboxApiKeyDenied",
    "verify_durable_sandbox_api_key",
]
