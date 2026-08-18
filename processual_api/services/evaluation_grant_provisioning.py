from __future__ import annotations

import base64
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from processual_api.db.session import get_session_factory
from processual_api.services.evaluation_grant_persistence import (
    EvaluationApiKeyAuthority,
    EvaluationGrantAuthority,
    SqlAlchemyEvaluationAuthorityRepository,
)


class EvaluationGrantProvisioningError(RuntimeError):
    """Durable evaluation authority cannot safely complete the requested mutation."""


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


def _compact_json(values: list[str]) -> str:
    return json.dumps(values, separators=(",", ":"), ensure_ascii=False)


def safe_evaluation_grant_payload(grant: EvaluationGrantAuthority) -> dict[str, Any]:
    return {
        "grant_id": grant.grant_ref,
        "status": grant.status,
        "client_id": grant.client_ref,
        "user_id": grant.user_ref,
        "issued_to": grant.issued_to,
        "purpose": grant.purpose,
        "allowed_task_ids": list(grant.allowed_task_ids),
        "task_scope_ids": list(grant.task_scope_ids),
        "allowed_scopes": list(grant.allowed_scopes),
        "max_requests": int(grant.max_requests),
        "used_requests": int(grant.used_requests),
        "rejected_requests": int(grant.rejected_requests),
        "created_at": grant.created_at.isoformat() if grant.created_at else "",
        "expires_at": grant.expires_at.isoformat(),
        "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
        "approved_by": grant.approved_by_actor_ref,
        "approved_by_role": grant.approved_by_role,
        "subscription_required": False,
        "entitlement_source": "admin_evaluation_grant",
        "task_authority_source": "integration_task_catalog",
        "quota_source": "evaluation_usage_ledger",
        "production_allowed": False,
        "runtime_connector_approved": False,
    }


def safe_evaluation_key_payload(
    key: EvaluationApiKeyAuthority,
    *,
    grant_ref: str,
    max_requests: int,
) -> dict[str, Any]:
    return {
        "key_id": key.key_ref,
        "prefix": key.key_prefix + "...",
        "category": "pilot_client",
        "client_id": key.client_ref,
        "evaluation_grant_id": grant_ref,
        "scopes": list(key.scopes),
        "allowed_task_ids": list(key.allowed_task_ids),
        "task_scope_ids": list(key.task_scope_ids),
        "task_authority_source": "integration_task_catalog",
        "quota_limit": int(max_requests),
        "quota_source": "evaluation_usage_ledger",
        "expires_at": key.expires_at.isoformat(),
        "status": key.status,
        "subscription_required": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


async def create_durable_evaluation_grant(
    *,
    owner_user_ref: str,
    client_ref: str,
    user_ref: str,
    issued_to: str,
    purpose: str,
    allowed_task_ids: list[str],
    task_scope_ids: list[str],
    allowed_scopes: list[str],
    max_requests: int,
    expires_in_days: int,
    approved_by_actor_ref: str,
    approved_by_role: str,
) -> dict[str, Any]:
    if max_requests <= 0:
        raise EvaluationGrantProvisioningError("evaluation_grant_quota_invalid")
    if expires_in_days <= 0:
        raise EvaluationGrantProvisioningError("evaluation_grant_expiry_invalid")

    now = datetime.now(UTC)
    grant = EvaluationGrantAuthority(
        id=uuid.uuid4(),
        grant_ref=f"eval_{secrets.token_hex(8)}",
        owner_user_ref=owner_user_ref,
        client_ref=client_ref,
        user_ref=user_ref,
        issued_to=issued_to,
        purpose=purpose,
        allowed_task_ids_json=_compact_json(allowed_task_ids),
        task_scope_ids_json=_compact_json(task_scope_ids),
        allowed_scopes_json=_compact_json(allowed_scopes),
        max_requests=max_requests,
        used_requests=0,
        rejected_requests=0,
        status="active",
        approved_by_actor_ref=approved_by_actor_ref,
        approved_by_role=approved_by_role,
        expires_at=now + timedelta(days=expires_in_days),
    )
    session_factory = get_session_factory()
    async with session_factory() as session:
        SqlAlchemyEvaluationAuthorityRepository(session).add(grant)
        await session.flush()
        await session.commit()
        return safe_evaluation_grant_payload(grant)


async def list_durable_evaluation_grants(*, owner_user_ref: str) -> list[dict[str, Any]]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyEvaluationAuthorityRepository(session)
        grants = await repository.list_grants_for_owner(owner_user_ref)
        changed = False
        result: list[dict[str, Any]] = []
        for grant in grants:
            before = grant.status
            grant.refresh_status()
            changed = changed or before != grant.status
            payload = safe_evaluation_grant_payload(grant)
            active_keys = await repository.active_keys_for_grant(grant.id)
            payload["active_key_count"] = len(active_keys)
            result.append(payload)
        if changed:
            await session.commit()
        return result


async def issue_durable_evaluation_key(
    *,
    grant_ref: str,
    owner_user_ref: str,
    label: str,
) -> tuple[dict[str, Any], str]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyEvaluationAuthorityRepository(session)
        grant = await repository.get_grant_by_ref(grant_ref, for_update=True)
        if grant is None or grant.owner_user_ref != owner_user_ref:
            raise EvaluationGrantProvisioningError("evaluation_grant_not_found")
        if grant.refresh_status() != "active":
            raise EvaluationGrantProvisioningError("evaluation_grant_inactive")

        active_keys = await repository.active_keys_for_grant(grant.id, for_update=True)
        if len(active_keys) >= 3:
            raise EvaluationGrantProvisioningError("maximum_active_evaluation_keys_reached")

        raw_key = _generate_raw_key()
        key = EvaluationApiKeyAuthority(
            id=uuid.uuid4(),
            key_ref=f"evalkey_{secrets.token_hex(8)}",
            grant_id=grant.id,
            key_hash=_hash_raw_key(raw_key),
            key_prefix=raw_key[:12],
            client_ref=grant.client_ref,
            user_ref=grant.user_ref,
            scopes_json=grant.allowed_scopes_json,
            allowed_task_ids_json=grant.allowed_task_ids_json,
            task_scope_ids_json=grant.task_scope_ids_json,
            label=label,
            status="enabled",
            expires_at=grant.expires_at,
            usage_count=0,
        )
        repository.add(key)
        await session.flush()
        await session.commit()
        return (
            safe_evaluation_key_payload(
                key,
                grant_ref=grant.grant_ref,
                max_requests=grant.max_requests,
            ),
            raw_key,
        )


async def revoke_durable_evaluation_grant(
    *,
    grant_ref: str,
    owner_user_ref: str,
) -> dict[str, Any]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SqlAlchemyEvaluationAuthorityRepository(session)
        grant = await repository.get_grant_by_ref(grant_ref, for_update=True)
        if grant is None or grant.owner_user_ref != owner_user_ref:
            raise EvaluationGrantProvisioningError("evaluation_grant_not_found")
        if grant.status == "revoked":
            return {
                "status": "revoked",
                "grant_id": grant.grant_ref,
                "revoked_at": grant.revoked_at.isoformat() if grant.revoked_at else None,
                "revoked_key_count": 0,
            }

        now = datetime.now(UTC)
        grant.status = "revoked"
        grant.revoked_at = now
        keys = await repository.active_keys_for_grant(grant.id, for_update=True)
        for key in keys:
            key.status = "revoked"
            key.revoked_at = now
        await session.commit()
        return {
            "status": "revoked",
            "grant_id": grant.grant_ref,
            "revoked_at": now.isoformat(),
            "revoked_key_count": len(keys),
        }


__all__ = [
    "EvaluationGrantProvisioningError",
    "create_durable_evaluation_grant",
    "issue_durable_evaluation_key",
    "list_durable_evaluation_grants",
    "revoke_durable_evaluation_grant",
    "safe_evaluation_grant_payload",
    "safe_evaluation_key_payload",
]
