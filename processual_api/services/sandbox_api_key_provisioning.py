from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from processual_api.admin_marketplace.models import AdminMarketPlan, AdminMarketSubscription
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.db.session import get_session_factory
from processual_api.services.sandbox_api_key_mode import durable_sandbox_api_keys_enabled
from processual_api.services.sandbox_api_key_persistence import (
    SandboxApiKeyAuthority,
    SqlAlchemySandboxApiKeyRepository,
)


class SandboxApiKeyProvisioningError(RuntimeError):
    """Durable sandbox key provisioning cannot safely complete."""


def durable_sandbox_api_key_provisioning_enabled() -> bool:
    return durable_sandbox_api_keys_enabled()


def _hash_raw_key(raw_key: str, *, iterations: int = 260_000) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        raw_key.encode("utf-8"),
        salt,
        iterations,
    )
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def _generate_raw_key() -> str:
    return f"pmk_{secrets.token_urlsafe(32)}"


def safe_durable_key_payload(key: SandboxApiKeyAuthority) -> dict[str, Any]:
    return {
        "key_id": str(key.id),
        "prefix": key.key_prefix + "...",
        "status": key.status,
        "profile_id": key.operational_profile_id,
        "label": key.label,
        "purpose": key.purpose,
        "environment": "sandbox",
        "scopes": list(key.scopes),
        "created_at": key.created_at.isoformat() if key.created_at else "",
        "expires_at": key.expires_at.isoformat(),
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "usage_count": int(key.usage_count or 0),
        "subscription_id": str(key.subscription_id),
        "plan_id": key.plan_id,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


async def _authoritative_subscription(
    session,
    *,
    client_ref: str,
    plan_code: str,
    for_update: bool,
) -> tuple[AdminMarketSubscription, AdminMarketPlan, AdminMarketSubscriptionRuntime]:
    statement = (
        select(AdminMarketSubscription, AdminMarketPlan, AdminMarketSubscriptionRuntime)
        .join(AdminMarketPlan, AdminMarketPlan.id == AdminMarketSubscription.plan_id)
        .join(
            AdminMarketSubscriptionRuntime,
            AdminMarketSubscriptionRuntime.subscription_id == AdminMarketSubscription.id,
        )
        .where(
            AdminMarketSubscription.customer_ref == client_ref,
            AdminMarketSubscription.status == "active",
            AdminMarketPlan.plan_code == plan_code,
            AdminMarketSubscriptionRuntime.customer_ref == client_ref,
            AdminMarketSubscriptionRuntime.access_stage.in_(("active", "grace")),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    rows = (await session.execute(statement)).all()
    if len(rows) != 1:
        raise SandboxApiKeyProvisioningError(
            "exactly_one_authoritative_active_subscription_required"
        )
    subscription, plan, runtime = rows[0]
    return subscription, plan, runtime


async def list_durable_sandbox_api_keys(
    *,
    client_ref: str,
    plan_code: str,
) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        await _authoritative_subscription(
            session,
            client_ref=client_ref,
            plan_code=plan_code,
            for_update=False,
        )
        repository = SqlAlchemySandboxApiKeyRepository(session)
        keys = await repository.list_active_for_client(client_ref)
        return [safe_durable_key_payload(key) for key in keys]


async def issue_durable_sandbox_api_key(
    *,
    client_ref: str,
    owner_user_ref: str,
    plan_code: str,
    profile_id: str,
    scopes: list[str],
    label: str,
    purpose: str,
    expires_in_days: int,
    issued_by_actor_ref: str,
) -> tuple[dict[str, Any], str]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        subscription, _plan, _runtime = await _authoritative_subscription(
            session,
            client_ref=client_ref,
            plan_code=plan_code,
            for_update=True,
        )
        repository = SqlAlchemySandboxApiKeyRepository(session)
        active = await repository.list_active_for_client(client_ref)
        if len(active) >= 3:
            raise SandboxApiKeyProvisioningError("maximum_active_sandbox_keys_reached")

        raw_key = _generate_raw_key()
        now = datetime.now(UTC)
        key = SandboxApiKeyAuthority(
            id=uuid.uuid4(),
            key_hash=_hash_raw_key(raw_key),
            key_prefix=raw_key[:12],
            client_ref=client_ref,
            owner_user_ref=owner_user_ref,
            subscription_id=subscription.id,
            plan_id=plan_code,
            operational_profile_id=profile_id,
            scopes_json=json.dumps(scopes, separators=(",", ":")),
            label=label,
            purpose=purpose,
            issued_to=client_ref,
            issued_by_actor_ref=issued_by_actor_ref,
            environment="sandbox",
            status="enabled",
            expires_at=now + timedelta(days=expires_in_days),
            usage_count=0,
        )
        repository.add(key)
        await session.flush()
        await session.commit()
        return safe_durable_key_payload(key), raw_key


async def revoke_durable_sandbox_api_key(
    *,
    key_id: str,
    client_ref: str,
    plan_code: str,
) -> dict[str, Any]:
    try:
        parsed_key_id = uuid.UUID(key_id)
    except (TypeError, ValueError) as exc:
        raise SandboxApiKeyProvisioningError("sandbox_key_not_found") from exc

    session_factory = get_session_factory()
    async with session_factory() as session:
        subscription, _plan, _runtime = await _authoritative_subscription(
            session,
            client_ref=client_ref,
            plan_code=plan_code,
            for_update=True,
        )
        repository = SqlAlchemySandboxApiKeyRepository(session)
        key = await repository.get_by_id(parsed_key_id, for_update=True)
        if (
            key is None
            or key.client_ref != client_ref
            or key.subscription_id != subscription.id
            or key.environment != "sandbox"
            or key.status != "enabled"
            or key.revoked_at is not None
        ):
            raise SandboxApiKeyProvisioningError("sandbox_key_not_found")
        key.mark_revoked()
        await session.commit()
        return safe_durable_key_payload(key)


async def rotate_durable_sandbox_api_key(
    *,
    key_id: str,
    client_ref: str,
    owner_user_ref: str,
    plan_code: str,
    expires_in_days: int,
    issued_by_actor_ref: str,
) -> tuple[dict[str, Any], str]:
    try:
        parsed_key_id = uuid.UUID(key_id)
    except (TypeError, ValueError) as exc:
        raise SandboxApiKeyProvisioningError("sandbox_key_not_found") from exc

    session_factory = get_session_factory()
    async with session_factory() as session:
        subscription, _plan, _runtime = await _authoritative_subscription(
            session,
            client_ref=client_ref,
            plan_code=plan_code,
            for_update=True,
        )
        repository = SqlAlchemySandboxApiKeyRepository(session)
        old_key = await repository.get_by_id(parsed_key_id, for_update=True)
        if (
            old_key is None
            or old_key.client_ref != client_ref
            or old_key.subscription_id != subscription.id
            or old_key.environment != "sandbox"
            or old_key.status != "enabled"
            or old_key.revoked_at is not None
        ):
            raise SandboxApiKeyProvisioningError("sandbox_key_not_found")

        raw_key = _generate_raw_key()
        now = datetime.now(UTC)
        old_key.mark_revoked(at=now)
        new_key = SandboxApiKeyAuthority(
            id=uuid.uuid4(),
            key_hash=_hash_raw_key(raw_key),
            key_prefix=raw_key[:12],
            client_ref=client_ref,
            owner_user_ref=owner_user_ref,
            subscription_id=subscription.id,
            plan_id=plan_code,
            operational_profile_id=old_key.operational_profile_id,
            scopes_json=old_key.scopes_json,
            label=old_key.label,
            purpose=old_key.purpose,
            issued_to=client_ref,
            issued_by_actor_ref=issued_by_actor_ref,
            environment="sandbox",
            status="enabled",
            expires_at=now + timedelta(days=expires_in_days),
            usage_count=0,
        )
        repository.add(new_key)
        await session.flush()
        await session.commit()
        return safe_durable_key_payload(new_key), raw_key


__all__ = [
    "SandboxApiKeyProvisioningError",
    "durable_sandbox_api_key_provisioning_enabled",
    "issue_durable_sandbox_api_key",
    "list_durable_sandbox_api_keys",
    "revoke_durable_sandbox_api_key",
    "rotate_durable_sandbox_api_key",
    "safe_durable_key_payload",
]
