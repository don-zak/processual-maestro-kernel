from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from processual_api.billing.commercial_public_catalog import public_commercial_plan_detail
from processual_api.db.session import get_session_factory

from .contracts import IntentCreate, IntentUpdate, IntentView, JourneyState, JourneyStep, ResumeView
from .models import JourneyCheckpointRow, RegistrationIntentRow

router = APIRouter(prefix="/registration", tags=["registration-journey"])


def _binding(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _view(intent: RegistrationIntentRow, checkpoint: JourneyCheckpointRow) -> IntentView:
    return IntentView(
        intent_id=intent.intent_id,
        plan_id=intent.plan_id,
        plan_slug=intent.plan_slug,
        catalog_version=intent.catalog_version,
        source_context=intent.source_context,
        billing_cycle=intent.billing_cycle,
        account_type=intent.account_type,
        state=intent.state,
        current_step=checkpoint.current_step,
        recovery_action=checkpoint.recovery_action,
        version=intent.version,
        expires_at=intent.expires_at,
        created_at=intent.created_at,
        updated_at=intent.updated_at,
    )


async def _owned(session, intent_id, session_token):
    intent = await session.get(RegistrationIntentRow, intent_id)
    if intent is None:
        raise HTTPException(status_code=404, detail="Journey intent not found")
    if intent.session_binding_hash != _binding(session_token):
        raise HTTPException(status_code=403, detail="Journey access denied")
    if intent.expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Journey intent expired")
    checkpoint = await session.scalar(select(JourneyCheckpointRow).where(JourneyCheckpointRow.intent_id == intent_id))
    if checkpoint is None:
        raise HTTPException(status_code=409, detail="Journey checkpoint missing")
    return intent, checkpoint


@router.post("/intents", response_model=IntentView, status_code=201)
async def create_intent(payload: IntentCreate):
    plan = public_commercial_plan_detail(payload.plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Commercial plan not found")

    now = datetime.now(UTC)
    binding = _binding(payload.session_token)
    async with get_session_factory()() as session:
        existing = await session.scalar(
            select(RegistrationIntentRow).where(
                RegistrationIntentRow.session_binding_hash == binding,
                RegistrationIntentRow.plan_id == payload.plan_id,
            )
        )
        if existing is not None and existing.expires_at > now:
            checkpoint = await session.scalar(
                select(JourneyCheckpointRow).where(JourneyCheckpointRow.intent_id == existing.intent_id)
            )
            return _view(existing, checkpoint)

        intent = RegistrationIntentRow(
            intent_id=uuid.uuid4(),
            plan_id=payload.plan_id,
            plan_slug=payload.plan_id,
            catalog_version=str(plan["catalog_version"]),
            source_context=payload.source_context,
            state=JourneyState.PLAN_SELECTED.value,
            session_binding_hash=binding,
            version=0,
            expires_at=now + timedelta(hours=24),
            created_at=now,
            updated_at=now,
        )
        checkpoint = JourneyCheckpointRow(
            checkpoint_id=uuid.uuid4(),
            intent_id=intent.intent_id,
            current_step=JourneyStep.ACCOUNT_TYPE.value,
            recovery_action="choose_account_type",
            state_version=0,
            last_valid_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add_all([intent, checkpoint])
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Journey creation conflict") from exc
        return _view(intent, checkpoint)


@router.get("/intents/{intent_id}", response_model=IntentView)
async def get_intent(intent_id: uuid.UUID, session_token: str):
    async with get_session_factory()() as session:
        intent, checkpoint = await _owned(session, intent_id, session_token)
        return _view(intent, checkpoint)


@router.patch("/intents/{intent_id}", response_model=IntentView)
async def update_intent(intent_id: uuid.UUID, payload: IntentUpdate):
    async with get_session_factory()() as session:
        intent, checkpoint = await _owned(session, intent_id, payload.session_token)
        if intent.version != payload.version:
            raise HTTPException(status_code=409, detail="Journey version conflict")
        if payload.account_type is not None:
            intent.account_type = payload.account_type.value
            intent.state = JourneyState.REGISTRATION_PENDING.value
            checkpoint.current_step = JourneyStep.REGISTRATION.value
            checkpoint.recovery_action = "continue_registration"
        if payload.billing_cycle is not None:
            intent.billing_cycle = payload.billing_cycle.value
        intent.version += 1
        checkpoint.state_version = intent.version
        checkpoint.last_valid_at = datetime.now(UTC)
        await session.commit()
        return _view(intent, checkpoint)


@router.get("/intents/{intent_id}/resume", response_model=ResumeView)
async def resume_intent(intent_id: uuid.UUID, session_token: str):
    async with get_session_factory()() as session:
        intent, checkpoint = await _owned(session, intent_id, session_token)
        view = _view(intent, checkpoint)
        return ResumeView(
            intent=view,
            resume_url=f"/register?journey_intent={intent.intent_id}&plan={intent.plan_id}",
        )
