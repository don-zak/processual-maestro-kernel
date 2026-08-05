from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.errors import (
    CommercialOrderNotFoundError,
    ContractCompletionConflictError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketContract,
)
from processual_api.admin_marketplace.notification_outbox import (
    enqueue_commercial_notification,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)


@dataclass(frozen=True, slots=True)
class ContractCompletionResult:
    contract_id: uuid.UUID
    contract_ref: str
    order_ref: str
    contract_version: str
    status: str
    acceptance_method: str
    evidence_reference: str
    completed_at: datetime
    order_status: str
    payment_status: str
    payment_reference: str | None
    payment_destination_snapshot: dict[str, object]
    reason_code: str


class DirectContractCompletionService:
    """Completes authenticated direct-order clickwrap contracts atomically."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdminMarketplaceUnitOfWork],
        clock: Callable[[], datetime],
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        reference_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        event_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_factory = id_factory
        self._reference_factory = reference_factory
        self._event_id_factory = event_id_factory

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Contract completion clock must be timezone-aware.")
        return now

    async def complete_authenticated_clickwrap(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        order_ref: str,
        contract_version: str,
        correlation_id: str,
        idempotency_key: str,
    ) -> ContractCompletionResult:
        actor_user_id = _required(actor_user_id, "actor_user_id")
        actor_session_id = _required(actor_session_id, "actor_session_id")
        customer_ref = _required(customer_ref, "customer_ref")
        order_ref = _required(order_ref, "order_ref").lower()
        contract_version = _required(contract_version, "contract_version").lower()
        correlation_id = _required(correlation_id, "correlation_id")
        idempotency_hash = _idempotency_hash(idempotency_key)
        now = self._now()

        try:
            return await self._complete_once(
                actor_user_id=actor_user_id,
                actor_session_id=actor_session_id,
                customer_ref=customer_ref,
                order_ref=order_ref,
                contract_version=contract_version,
                correlation_id=correlation_id,
                idempotency_hash=idempotency_hash,
                now=now,
            )
        except AdminMarketplaceConflictError:
            replay = await self._completed_result(
                customer_ref=customer_ref,
                order_ref=order_ref,
                contract_version=contract_version,
                reason_code="contract_completion_idempotent",
            )
            if replay is None:
                raise
            return replay

    async def _complete_once(
        self,
        *,
        actor_user_id: str,
        actor_session_id: str,
        customer_ref: str,
        order_ref: str,
        contract_version: str,
        correlation_id: str,
        idempotency_hash: str,
        now: datetime,
    ) -> ContractCompletionResult:
        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_ref(order_ref, for_update=True)
            _require_customer_order(order, customer_ref)
            existing = await unit.contracts.get_by_order_id(
                order.id,
                for_update=True,
            )
            if existing is not None:
                _require_same_contract(existing, contract_version)
                return _result(
                    existing,
                    order,
                    "contract_completion_idempotent",
                )

            expected_version = str(
                order.offer_snapshot.get("contract_version", "")
            ).strip().lower()
            if not expected_version or contract_version != expected_version:
                raise ContractCompletionConflictError(
                    "Contract version does not match the order snapshot."
                )
            if order.selected_channel != "maestro_direct":
                raise ContractCompletionConflictError(
                    "Order does not use the direct sales channel."
                )
            if order.status != "awaiting_contract" or order.contract_status != "pending":
                raise ContractCompletionConflictError(
                    "Order is not awaiting contract completion."
                )

            previous_digest = _digest(_order_contract_state(order))
            token = self._reference_factory().hex
            contract = AdminMarketContract(
                id=self._id_factory(),
                contract_ref=f"ctr_{token[:24]}",
                order_id=order.id,
                customer_ref=customer_ref,
                contract_version=contract_version,
                status="completed",
                accepted_party_ref=actor_user_id,
                acceptance_method="authenticated_clickwrap",
                evidence_reference=f"cev_{token[24:32]}",
                completion_idempotency_key_hash=idempotency_hash,
                completed_at=now,
                created_at=now,
            )
            order.contract_status = "completed"
            order.status = "awaiting_payment"
            order.updated_at = now
            unit.contracts.add(contract)
            unit.commercial_audit.append(
                self._audit(
                    contract=contract,
                    order=order,
                    actor_user_id=actor_user_id,
                    actor_session_id=actor_session_id,
                    correlation_id=correlation_id,
                    previous_digest=previous_digest,
                    occurred_at=now,
                )
            )
            enqueue_commercial_notification(
                unit,
                event_type="contract_completed",
                aggregate_type="order",
                aggregate_ref=order.order_ref,
                customer_ref=order.customer_ref,
                payload={
                    "order_ref": order.order_ref,
                    "contract_ref": contract.contract_ref,
                    "contract_version": contract.contract_version,
                },
                deduplication_material=contract.completion_idempotency_key_hash,
                occurred_at=now,
            )
            enqueue_commercial_notification(
                unit,
                event_type="payment_instructions_ready",
                aggregate_type="order",
                aggregate_ref=order.order_ref,
                customer_ref=order.customer_ref,
                payload={
                    "order_ref": order.order_ref,
                    "currency": "TND",
                    "status": order.status,
                },
                deduplication_material=contract.completion_idempotency_key_hash,
                occurred_at=now,
            )
            await unit.commit()
            return _result(contract, order, "contract_completed")

    async def _completed_result(
        self,
        *,
        customer_ref: str,
        order_ref: str,
        contract_version: str,
        reason_code: str,
    ) -> ContractCompletionResult | None:
        async with self._unit_of_work_factory() as unit:
            order = await unit.orders.get_by_ref(order_ref)
            _require_customer_order(order, customer_ref)
            contract = await unit.contracts.get_by_order_id(order.id)
        if contract is None:
            return None
        _require_same_contract(contract, contract_version)
        return _result(contract, order, reason_code)

    def _audit(
        self,
        *,
        contract: AdminMarketContract,
        order,
        actor_user_id: str,
        actor_session_id: str,
        correlation_id: str,
        previous_digest: str,
        occurred_at: datetime,
    ) -> AdminMarketAuditRecord:
        record = CommercialAuditRecord(
            event_id=str(self._event_id_factory()),
            occurred_at=occurred_at,
            actor_user_id=actor_user_id,
            actor_session_id=actor_session_id,
            platform_authority="identity_customer",
            action=CommercialAuditAction.CONTRACT_COMPLETED,
            resource_type=CommercialResourceType.CONTRACT,
            resource_id=contract.contract_ref,
            outcome=CommercialAuditOutcome.ALLOWED,
            reason_code="contract_completed",
            correlation_id=correlation_id,
            previous_state_digest=previous_digest,
            new_state_digest=_digest(_order_contract_state(order)),
            metadata={
                "order_ref": order.order_ref,
                "contract_version": contract.contract_version,
                "acceptance_method": contract.acceptance_method,
            },
        )
        return AdminMarketAuditRecord(
            id=uuid.UUID(record.event_id),
            event_ref=record.event_id,
            occurred_at=record.occurred_at,
            actor_user_id=record.actor_user_id,
            actor_session_id=record.actor_session_id,
            platform_authority=record.platform_authority,
            action=record.action.value,
            resource_type=record.resource_type.value,
            resource_id=record.resource_id,
            outcome=record.outcome.value,
            reason_code=record.reason_code,
            correlation_id=record.correlation_id,
            previous_state_digest=record.previous_state_digest,
            new_state_digest=record.new_state_digest,
            metadata_json=dict(record.metadata),
            created_at=record.occurred_at,
        )


def _required(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required.")
    return normalized


def _idempotency_hash(value: str) -> str:
    normalized = value.strip()
    if len(normalized) < 16 or len(normalized) > 128:
        raise ValueError("idempotency_key is invalid.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _require_customer_order(order, customer_ref: str) -> None:
    if order is None or order.customer_ref != customer_ref:
        raise CommercialOrderNotFoundError("Commercial order was not found.")


def _require_same_contract(contract, contract_version: str) -> None:
    if (
        contract.contract_version != contract_version
        or contract.status != "completed"
        or contract.acceptance_method != "authenticated_clickwrap"
    ):
        raise ContractCompletionConflictError(
            "Stored contract conflicts with the completion request."
        )


def _order_contract_state(order) -> dict[str, object]:
    return {
        "order_ref": order.order_ref,
        "status": order.status,
        "contract_status": order.contract_status,
        "payment_status": order.payment_status,
    }


def _digest(value: dict[str, object]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _result(contract, order, reason_code: str) -> ContractCompletionResult:
    return ContractCompletionResult(
        contract_id=contract.id,
        contract_ref=contract.contract_ref,
        order_ref=order.order_ref,
        contract_version=contract.contract_version,
        status=contract.status,
        acceptance_method=contract.acceptance_method,
        evidence_reference=contract.evidence_reference,
        completed_at=contract.completed_at,
        order_status=order.status,
        payment_status=order.payment_status,
        payment_reference=order.payment_reference,
        payment_destination_snapshot=dict(order.payment_destination_snapshot),
        reason_code=reason_code,
    )


__all__ = ["ContractCompletionResult", "DirectContractCompletionService"]
