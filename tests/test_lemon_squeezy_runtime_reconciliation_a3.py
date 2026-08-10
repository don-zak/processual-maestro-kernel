from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.lemon_squeezy_runtime_reconciliation import (
    apply_lemon_squeezy_runtime_access,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
SUBSCRIPTION_ID = uuid.UUID("00000000-0000-0000-0000-000000000201")
RUNTIME_ID = uuid.UUID("00000000-0000-0000-0000-000000000202")
DECISION_ID = uuid.UUID("00000000-0000-0000-0000-000000000203")


class RuntimeRepository:
    def __init__(self, runtime: object | None) -> None:
        self.runtime = runtime

    async def get_by_subscription_id(
        self,
        subscription_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        if self.runtime is None or self.runtime.subscription_id != subscription_id:
            return None
        return self.runtime


class TransitionRepository:
    def __init__(self, existing: object | None = None) -> None:
        self.existing = existing
        self.added: list[object] = []

    async def get_by_decision_id(
        self,
        decision_id: uuid.UUID,
        *,
        for_update: bool = False,
    ):
        return self.existing

    def add(self, transition: object) -> None:
        self.added.append(transition)


def _uow(runtime: object | None, existing: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        subscription_runtime=RuntimeRepository(runtime),
        subscription_runtime_transitions=TransitionRepository(existing),
    )


def _binding() -> SimpleNamespace:
    return SimpleNamespace(subscription_id=SUBSCRIPTION_ID)


def _subscription(status: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=SUBSCRIPTION_ID,
        customer_ref="customer_001",
        status=status,
    )


def _runtime(stage: str = "active", **overrides: object) -> SimpleNamespace:
    values = {
        "id": RUNTIME_ID,
        "subscription_id": SUBSCRIPTION_ID,
        "customer_ref": "customer_001",
        "access_stage": stage,
        "version": 4,
        "effective_at": NOW - timedelta(hours=1),
        "grace_until": NOW + timedelta(hours=2),
        "suspended_at": None,
        "terminated_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _inbox(event_name: str = "subscription_updated", **overrides: object) -> SimpleNamespace:
    values = {"event_name": event_name, "provider_effective_at": NOW}
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subscription_status", "expected_stage"),
    [
        ("active", "active"),
        ("suspended", "suspended"),
        ("cancelled", "terminated"),
        ("expired", "terminated"),
    ],
)
async def test_subscription_status_controls_runtime_access(
    subscription_status: str,
    expected_stage: str,
) -> None:
    runtime = _runtime(stage="active")
    uow = _uow(runtime)

    await apply_lemon_squeezy_runtime_access(
        uow=uow,
        binding=_binding(),
        subscription=_subscription(subscription_status),
        inbox=_inbox(),
        reconciliation_decision_id=DECISION_ID,
    )

    assert runtime.access_stage == expected_stage
    assert len(uow.subscription_runtime_transitions.added) == 1
    transition = uow.subscription_runtime_transitions.added[0]
    assert transition.from_stage == "active"
    assert transition.to_stage == expected_stage


@pytest.mark.asyncio
async def test_runtime_mutation_is_idempotent_by_decision() -> None:
    runtime = _runtime(stage="suspended")
    uow = _uow(runtime, existing=SimpleNamespace(id=uuid.uuid4()))

    await apply_lemon_squeezy_runtime_access(
        uow=uow,
        binding=_binding(),
        subscription=_subscription("active"),
        inbox=_inbox(),
        reconciliation_decision_id=DECISION_ID,
    )

    assert runtime.access_stage == "suspended"
    assert runtime.version == 4
    assert uow.subscription_runtime_transitions.added == []


@pytest.mark.asyncio
async def test_terminated_runtime_cannot_be_reactivated() -> None:
    runtime = _runtime(stage="terminated", terminated_at=NOW - timedelta(hours=1))
    uow = _uow(runtime)

    with pytest.raises(LemonSqueezyWebhookError, match="cannot be reactivated"):
        await apply_lemon_squeezy_runtime_access(
            uow=uow,
            binding=_binding(),
            subscription=_subscription("active"),
            inbox=_inbox(),
            reconciliation_decision_id=DECISION_ID,
        )

    assert uow.subscription_runtime_transitions.added == []


@pytest.mark.asyncio
async def test_runtime_watermark_cannot_move_backwards() -> None:
    runtime = _runtime(effective_at=NOW)
    uow = _uow(runtime)

    with pytest.raises(LemonSqueezyWebhookError, match="older than current state"):
        await apply_lemon_squeezy_runtime_access(
            uow=uow,
            binding=_binding(),
            subscription=_subscription("suspended"),
            inbox=_inbox(provider_effective_at=NOW - timedelta(minutes=1)),
            reconciliation_decision_id=DECISION_ID,
        )

    assert runtime.access_stage == "active"
    assert uow.subscription_runtime_transitions.added == []


@pytest.mark.asyncio
async def test_missing_runtime_fails_closed() -> None:
    uow = _uow(None)

    with pytest.raises(LemonSqueezyWebhookError, match="runtime was not found"):
        await apply_lemon_squeezy_runtime_access(
            uow=uow,
            binding=_binding(),
            subscription=_subscription("active"),
            inbox=_inbox(),
            reconciliation_decision_id=DECISION_ID,
        )
