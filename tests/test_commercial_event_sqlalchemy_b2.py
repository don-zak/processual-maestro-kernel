from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.billing.commercial_event_models import CommercialEventRecord
from processual_api.billing.commercial_event_repository import (
    SqlAlchemyCommercialEventRepository,
)
from processual_api.billing.commercial_state_machine import CommercialAggregate
from processual_api.billing.commercial_top_up_event_ledger import stage_top_up_events
from processual_api.billing.commercial_top_up_transition_authority import (
    TopUpTransitionEvidence,
    build_verified_payment_grant_events,
)
from processual_api.billing.commercial_top_up_unit_of_work import (
    SqlAlchemyCommercialTopUpUnitOfWork,
)


def _events():
    return build_verified_payment_grant_events(
        TopUpTransitionEvidence(
            order_id=uuid4(),
            provider_reference="provider-payment-001",
            actor_reference="payment-verifier:test",
            evidence_reference="audit://payment/001",
            occurred_at=datetime(2026, 8, 10, 10, 0, tzinfo=UTC),
            payment_payload_digest="sha256:payment",
            grant_payload_digest="sha256:grant",
        )
    )


async def _session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(CommercialEventRecord.__table__.create)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_commercial_event_model_has_unique_and_append_only_guards() -> None:
    constraints = {
        constraint.name for constraint in CommercialEventRecord.__table__.constraints
    }

    assert CommercialEventRecord.__tablename__ == "commercial_events"
    assert "uq_commercial_events_canonical_idempotency_key" in constraints
    assert CommercialEventRecord.__mapper__.dispatch.before_update
    assert CommercialEventRecord.__mapper__.dispatch.before_delete


@pytest.mark.asyncio
async def test_repository_round_trips_authoritative_event_chain() -> None:
    engine, session_factory = await _session_factory()
    events = _events()
    try:
        async with session_factory() as session:
            repository = SqlAlchemyCommercialEventRepository(session)
            result = await stage_top_up_events(repository=repository, events=events)
            await session.commit()

            assert result.appended == events
            assert result.replayed == ()

        async with session_factory() as session:
            repository = SqlAlchemyCommercialEventRepository(session)
            stored = await repository.list_for_aggregate(
                CommercialAggregate.TOP_UP,
                events[0].aggregate_id,
            )

        assert [event.current_state for event in stored] == [
            "awaiting_payment",
            "payment_pending",
            "payment_verified",
            "grant_pending",
        ]
        assert [event.next_state for event in stored] == [
            "payment_pending",
            "payment_verified",
            "grant_pending",
            "granted",
        ]
        assert all(event.occurred_at.tzinfo is not None for event in stored)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unique_canonical_idempotency_key_is_enforced_by_storage() -> None:
    engine, session_factory = await _session_factory()
    event = _events()[0]
    conflicting = replace(event, event_id=uuid4(), actor_reference="other-actor")
    try:
        async with session_factory() as session:
            repository = SqlAlchemyCommercialEventRepository(session)
            repository.append(event)
            await session.commit()

        async with session_factory() as session:
            repository = SqlAlchemyCommercialEventRepository(session)
            repository.append(conflicting)
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_top_up_uow_rolls_back_uncommitted_ledger_events() -> None:
    engine, session_factory = await _session_factory()
    events = _events()
    try:
        async with SqlAlchemyCommercialTopUpUnitOfWork(session_factory) as uow:
            await stage_top_up_events(repository=uow.event_ledger, events=events)

        async with session_factory() as session:
            repository = SqlAlchemyCommercialEventRepository(session)
            stored = await repository.list_for_aggregate(
                CommercialAggregate.TOP_UP,
                events[0].aggregate_id,
            )

        assert stored == ()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_top_up_uow_commits_ledger_events_in_its_transaction() -> None:
    engine, session_factory = await _session_factory()
    events = _events()
    try:
        async with SqlAlchemyCommercialTopUpUnitOfWork(session_factory) as uow:
            await stage_top_up_events(repository=uow.event_ledger, events=events)
            await uow.commit()

        async with session_factory() as session:
            repository = SqlAlchemyCommercialEventRepository(session)
            stored = await repository.list_for_aggregate(
                CommercialAggregate.TOP_UP,
                events[0].aggregate_id,
            )

        assert len(stored) == 4
        assert stored[-1].next_state == "granted"
    finally:
        await engine.dispose()
