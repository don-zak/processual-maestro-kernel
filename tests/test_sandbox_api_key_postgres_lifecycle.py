from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from processual_api.admin_marketplace.models import (
    AdminMarketPlan,
    AdminMarketSubscription,
)
from processual_api.admin_marketplace.subscription_runtime_persistence import (
    AdminMarketSubscriptionRuntime,
)
from processual_api.db.session import get_session_factory
from processual_api.services.sandbox_api_key_authority import (
    DurableSandboxApiKeyDenied,
    verify_durable_sandbox_api_key,
)
from processual_api.services.sandbox_api_key_persistence import SandboxApiKeyAuthority
from processual_api.services.sandbox_api_key_provisioning import (
    issue_durable_sandbox_api_key,
    revoke_durable_sandbox_api_key,
    rotate_durable_sandbox_api_key,
)


_DATABASE_URL = os.environ.get("DATABASE_URL", "").lower()
pytestmark = pytest.mark.skipif(
    not _DATABASE_URL.startswith(("postgresql://", "postgresql+asyncpg://")),
    reason="PostgreSQL sandbox-key lifecycle qualification requires DATABASE_URL",
)


@pytest.mark.asyncio
async def test_durable_sandbox_key_full_lifecycle_is_fail_closed() -> None:
    plan_id = uuid.uuid4()
    subscription_id = uuid.uuid4()
    runtime_id = uuid.uuid4()
    suffix = uuid.uuid4().hex
    customer_ref = f"qualification-key-customer-{suffix}"
    owner_ref = f"qualification-user-{suffix}"
    plan_code = f"qualification-key-plan-{suffix}"
    now = datetime.now(UTC)

    session_factory = get_session_factory()
    async with session_factory() as session:
        session.add(
            AdminMarketPlan(
                id=plan_id,
                plan_code=plan_code,
                display_name="Sandbox API-key lifecycle qualification",
                entitlement_profile_ref="qualification_entitlements",
                quota_profile_ref="qualification_quota",
                metadata_json={},
            )
        )
        session.add(
            AdminMarketSubscription(
                id=subscription_id,
                subscription_ref=f"qualification-key-subscription-{suffix}",
                customer_ref=customer_ref,
                order_id=None,
                offer_id=None,
                plan_id=plan_id,
                status="active",
                starts_at=now,
                ends_at=None,
            )
        )
        session.add(
            AdminMarketSubscriptionRuntime(
                id=runtime_id,
                subscription_id=subscription_id,
                customer_ref=customer_ref,
                entitlement_profile_ref="qualification_entitlements",
                quota_profile_ref="qualification_quota",
                access_stage="active",
                version=0,
                effective_at=now,
            )
        )
        await session.commit()

    issued_key_id: uuid.UUID | None = None
    rotated_key_id: uuid.UUID | None = None
    try:
        issued, raw_key = await issue_durable_sandbox_api_key(
            client_ref=customer_ref,
            owner_user_ref=owner_ref,
            plan_code=plan_code,
            profile_id="service_integration_read_only",
            scopes=["read:health"],
            label="Lifecycle qualification",
            purpose="PostgreSQL lifecycle proof",
            expires_in_days=7,
            issued_by_actor_ref=owner_ref,
        )
        issued_key_id = uuid.UUID(issued["key_id"])

        assert raw_key.startswith("pmk_")
        assert issued["raw_secret_visible"] is False
        assert raw_key not in repr(issued)
        assert issued["subscription_id"] == str(subscription_id)
        assert issued["production_allowed"] is False

        async with session_factory() as session:
            stored = await session.get(SandboxApiKeyAuthority, issued_key_id)
            assert stored is not None
            assert stored.key_hash != raw_key
            assert raw_key not in stored.key_hash
            assert stored.key_prefix == raw_key[:12]
            assert stored.environment == "sandbox"
            assert stored.subscription_id == subscription_id

        identity = await verify_durable_sandbox_api_key(raw_key)
        assert identity is not None
        assert identity["client_id"] == customer_ref
        assert identity["subscription_id"] == str(subscription_id)
        assert identity["session_type"] == "sandbox_api_key"
        assert identity["production_allowed"] is False

        rotated, rotated_raw_key = await rotate_durable_sandbox_api_key(
            key_id=str(issued_key_id),
            client_ref=customer_ref,
            owner_user_ref=owner_ref,
            plan_code=plan_code,
            expires_in_days=7,
            issued_by_actor_ref=owner_ref,
        )
        rotated_key_id = uuid.UUID(rotated["key_id"])
        assert rotated_raw_key.startswith("pmk_")
        assert rotated_raw_key != raw_key
        assert rotated_raw_key not in repr(rotated)

        with pytest.raises(DurableSandboxApiKeyDenied, match="revoked_or_disabled"):
            await verify_durable_sandbox_api_key(raw_key)

        rotated_identity = await verify_durable_sandbox_api_key(rotated_raw_key)
        assert rotated_identity is not None
        assert rotated_identity["api_key_id"] == str(rotated_key_id)

        revoked = await revoke_durable_sandbox_api_key(
            key_id=str(rotated_key_id),
            client_ref=customer_ref,
            plan_code=plan_code,
        )
        assert revoked["status"] == "revoked"
        assert revoked["raw_secret_visible"] is False

        with pytest.raises(DurableSandboxApiKeyDenied, match="revoked_or_disabled"):
            await verify_durable_sandbox_api_key(rotated_raw_key)
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(SandboxApiKeyAuthority).where(
                    SandboxApiKeyAuthority.subscription_id == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscriptionRuntime).where(
                    AdminMarketSubscriptionRuntime.subscription_id == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketSubscription).where(
                    AdminMarketSubscription.id == subscription_id
                )
            )
            await session.execute(
                delete(AdminMarketPlan).where(AdminMarketPlan.id == plan_id)
            )
            await session.commit()
