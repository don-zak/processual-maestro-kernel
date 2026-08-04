from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.errors import (
    PaymentDestinationConflictError,
    PaymentDestinationNotFoundError,
)
from processual_api.admin_marketplace.models import (
    AdminMarketAuditRecord,
    AdminMarketPaymentDestination,
)
from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationCreateContract,
    PaymentDestinationStatus,
    PaymentDestinationValidationMethod,
    validate_payment_destination_identifier,
)
from processual_api.admin_marketplace.payment_destination_crypto import (
    PaymentDestinationCipher,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)


@dataclass(frozen=True, slots=True)
class PaymentDestinationAdministrationResult:
    destination_id: uuid.UUID
    destination_ref: str
    status: PaymentDestinationStatus
    is_active: bool
    is_default: bool
    reason_code: str


class PaymentDestinationAdministrationService:
    """Secure administration of Tunisian maestro_direct payment destinations."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdminMarketplaceUnitOfWork],
        cipher: PaymentDestinationCipher,
        clock: Callable[[], datetime],
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        event_id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._cipher = cipher
        self._clock = clock
        self._id_factory = id_factory
        self._event_id_factory = event_id_factory

    async def create(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        command: PaymentDestinationCreateContract,
        correlation_id: str,
    ) -> PaymentDestinationAdministrationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.CREATE_PAYMENT_DESTINATION,
        )
        normalized_correlation_id = _required(
            correlation_id,
            field_name="correlation_id",
        )

        validation = validate_payment_destination_identifier(
            value=command.raw_account_identifier,
            destination_type=command.destination_type,
        )
        if (
            not validation.valid
            or validation.normalized_identifier is None
            or validation.masked_identifier is None
        ):
            raise PaymentDestinationConflictError(
                f"Payment destination identifier rejected: {validation.reason_code}."
            )

        destination_id = self._id_factory()
        now = self._now()

        encrypted = self._cipher.encrypt(
            validation.normalized_identifier,
            payment_destination_id=str(destination_id),
            destination_ref=command.destination_ref,
        )

        destination = AdminMarketPaymentDestination(
            id=destination_id,
            destination_ref=command.destination_ref,
            display_name=command.display_name,
            destination_type=command.destination_type.value,
            institution_name=command.institution_name,
            account_holder_name=command.account_holder_name,
            identifier_ciphertext=encrypted.ciphertext,
            identifier_key_version=encrypted.key_version,
            masked_identifier=validation.masked_identifier,
            country_code="TN",
            currency="TND",
            sales_channel="maestro_direct",
            status=PaymentDestinationStatus.DRAFT.value,
            validation_method=None,
            validation_reason_code=None,
            validated_at=None,
            is_active=False,
            is_default=False,
            effective_at=None,
            expires_at=None,
            instructions=command.instructions,
            created_at=now,
            updated_at=now,
        )

        async with self._unit_of_work_factory() as unit:
            existing = await unit.payment_destinations.get_by_ref(
                command.destination_ref,
                for_update=True,
            )
            if existing is not None:
                raise PaymentDestinationConflictError(
                    "Payment destination reference already exists."
                )

            unit.payment_destinations.add(destination)
            unit.commercial_audit.append(
                self._audit_model(
                    authority=authority,
                    action=CommercialAuditAction.PAYMENT_DESTINATION_CREATED,
                    destination=destination,
                    outcome=CommercialAuditOutcome.ALLOWED,
                    reason_code="payment_destination_created",
                    correlation_id=normalized_correlation_id,
                    previous_state=None,
                    new_state=_state_projection(destination),
                    occurred_at=now,
                )
            )
            await unit.commit()

        return _result(destination, "payment_destination_created")

    async def validate(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        destination_ref: str,
        correlation_id: str,
    ) -> PaymentDestinationAdministrationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VALIDATE_PAYMENT_DESTINATION,
        )
        destination_ref = _required(
            destination_ref,
            field_name="destination_ref",
        ).lower()
        correlation_id = _required(
            correlation_id,
            field_name="correlation_id",
        )
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            destination = await self._locked_destination(
                unit,
                destination_ref,
            )
            if destination.status != PaymentDestinationStatus.DRAFT.value:
                raise PaymentDestinationConflictError(
                    "Only a draft payment destination can be validated."
                )

            previous = _state_projection(destination)
            destination.status = PaymentDestinationStatus.VALIDATED.value
            destination.validation_method = (
                PaymentDestinationValidationMethod.STRUCTURAL.value
            )
            destination.validation_reason_code = "structurally_validated"
            destination.validated_at = now
            destination.updated_at = now

            unit.commercial_audit.append(
                self._audit_model(
                    authority=authority,
                    action=CommercialAuditAction.PAYMENT_DESTINATION_VALIDATED,
                    destination=destination,
                    outcome=CommercialAuditOutcome.ALLOWED,
                    reason_code="payment_destination_structurally_validated",
                    correlation_id=correlation_id,
                    previous_state=previous,
                    new_state=_state_projection(destination),
                    occurred_at=now,
                )
            )
            await unit.commit()

        return _result(
            destination,
            "payment_destination_structurally_validated",
        )

    async def activate(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        destination_ref: str,
        correlation_id: str,
    ) -> PaymentDestinationAdministrationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.ACTIVATE_PAYMENT_DESTINATION,
        )
        destination_ref = _required(
            destination_ref,
            field_name="destination_ref",
        ).lower()
        correlation_id = _required(
            correlation_id,
            field_name="correlation_id",
        )
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            destination = await self._locked_destination(
                unit,
                destination_ref,
            )
            if destination.status != PaymentDestinationStatus.VALIDATED.value:
                raise PaymentDestinationConflictError(
                    "Only a validated payment destination can be activated."
                )

            previous = _state_projection(destination)
            destination.status = PaymentDestinationStatus.ACTIVE.value
            destination.is_active = True
            destination.is_default = False
            destination.effective_at = now
            destination.expires_at = None
            destination.updated_at = now

            unit.commercial_audit.append(
                self._audit_model(
                    authority=authority,
                    action=CommercialAuditAction.PAYMENT_DESTINATION_ACTIVATED,
                    destination=destination,
                    outcome=CommercialAuditOutcome.ALLOWED,
                    reason_code="payment_destination_activated",
                    correlation_id=correlation_id,
                    previous_state=previous,
                    new_state=_state_projection(destination),
                    occurred_at=now,
                )
            )
            await unit.commit()

        return _result(destination, "payment_destination_activated")

    async def deactivate(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        destination_ref: str,
        correlation_id: str,
    ) -> PaymentDestinationAdministrationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.DEACTIVATE_PAYMENT_DESTINATION,
        )
        destination_ref = _required(
            destination_ref,
            field_name="destination_ref",
        ).lower()
        correlation_id = _required(
            correlation_id,
            field_name="correlation_id",
        )
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            destination = await self._locked_destination(
                unit,
                destination_ref,
            )
            if (
                destination.status != PaymentDestinationStatus.ACTIVE.value
                or not destination.is_active
            ):
                raise PaymentDestinationConflictError(
                    "Only an active payment destination can be deactivated."
                )

            previous = _state_projection(destination)
            destination.status = PaymentDestinationStatus.INACTIVE.value
            destination.is_active = False
            destination.is_default = False
            destination.expires_at = now
            destination.updated_at = now

            unit.commercial_audit.append(
                self._audit_model(
                    authority=authority,
                    action=CommercialAuditAction.PAYMENT_DESTINATION_DEACTIVATED,
                    destination=destination,
                    outcome=CommercialAuditOutcome.ALLOWED,
                    reason_code="payment_destination_deactivated",
                    correlation_id=correlation_id,
                    previous_state=previous,
                    new_state=_state_projection(destination),
                    occurred_at=now,
                )
            )
            await unit.commit()

        return _result(destination, "payment_destination_deactivated")

    async def set_default(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        destination_ref: str,
        correlation_id: str,
    ) -> PaymentDestinationAdministrationResult:
        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.SET_DEFAULT_PAYMENT_DESTINATION,
        )
        destination_ref = _required(
            destination_ref,
            field_name="destination_ref",
        ).lower()
        correlation_id = _required(
            correlation_id,
            field_name="correlation_id",
        )
        now = self._now()

        async with self._unit_of_work_factory() as unit:
            destination = await self._locked_destination(
                unit,
                destination_ref,
            )
            if (
                destination.status != PaymentDestinationStatus.ACTIVE.value
                or not destination.is_active
            ):
                raise PaymentDestinationConflictError(
                    "Only an active payment destination can become default."
                )

            current_default = await unit.payment_destinations.get_active_default(
                for_update=True,
            )

            if (
                current_default is not None
                and current_default.id == destination.id
                and destination.is_default
            ):
                return _result(
                    destination,
                    "payment_destination_already_default",
                )

            previous = _state_projection(destination)

            if (
                current_default is not None
                and current_default.id != destination.id
            ):
                current_default.is_default = False
                current_default.updated_at = now

            destination.is_default = True
            destination.updated_at = now

            unit.commercial_audit.append(
                self._audit_model(
                    authority=authority,
                    action=CommercialAuditAction.PAYMENT_DESTINATION_DEFAULT_SET,
                    destination=destination,
                    outcome=CommercialAuditOutcome.ALLOWED,
                    reason_code="payment_destination_default_set",
                    correlation_id=correlation_id,
                    previous_state=previous,
                    new_state=_state_projection(destination),
                    occurred_at=now,
                    metadata={
                        "previous_default_present": str(
                            current_default is not None
                        ).lower(),
                    },
                )
            )
            await unit.commit()

        return _result(
            destination,
            "payment_destination_default_set",
        )

    async def _locked_destination(
        self,
        unit: AdminMarketplaceUnitOfWork,
        destination_ref: str,
    ) -> AdminMarketPaymentDestination:
        destination = await unit.payment_destinations.get_by_ref(
            destination_ref,
            for_update=True,
        )
        if destination is None:
            raise PaymentDestinationNotFoundError(
                "Payment destination was not found."
            )
        return destination

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError(
                "Payment destination administration clock must be timezone-aware."
            )
        return value

    def _audit_model(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        action: CommercialAuditAction,
        destination: AdminMarketPaymentDestination,
        outcome: CommercialAuditOutcome,
        reason_code: str,
        correlation_id: str,
        previous_state: dict[str, Any] | None,
        new_state: dict[str, Any] | None,
        occurred_at: datetime,
        metadata: dict[str, str] | None = None,
    ) -> AdminMarketAuditRecord:
        contract = CommercialAuditRecord(
            event_id=f"payment-destination-event:{self._event_id_factory()}",
            occurred_at=occurred_at,
            actor_user_id=authority.user_id,
            actor_session_id=authority.session_id,
            platform_authority="platform_admin",
            action=action,
            resource_type=CommercialResourceType.PAYMENT_DESTINATION,
            resource_id=destination.destination_ref,
            outcome=outcome,
            reason_code=reason_code,
            correlation_id=correlation_id,
            previous_state_digest=_state_digest(previous_state),
            new_state_digest=_state_digest(new_state),
            metadata={
                "sales_channel": "maestro_direct",
                "country_code": "TN",
                "currency": "TND",
                **(metadata or {}),
            },
        )

        return AdminMarketAuditRecord(
            id=self._id_factory(),
            event_ref=contract.event_id,
            occurred_at=contract.occurred_at,
            actor_user_id=contract.actor_user_id,
            actor_session_id=contract.actor_session_id,
            platform_authority=contract.platform_authority,
            action=contract.action.value,
            resource_type=contract.resource_type.value,
            resource_id=contract.resource_id,
            outcome=contract.outcome.value,
            reason_code=contract.reason_code,
            correlation_id=contract.correlation_id,
            previous_state_digest=contract.previous_state_digest,
            new_state_digest=contract.new_state_digest,
            metadata_json=dict(contract.metadata),
            created_at=occurred_at,
        )


def _required(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    return normalized


def _state_projection(
    destination: AdminMarketPaymentDestination,
) -> dict[str, Any]:
    return {
        "destination_ref": destination.destination_ref,
        "destination_type": destination.destination_type,
        "country_code": destination.country_code,
        "currency": destination.currency,
        "sales_channel": destination.sales_channel,
        "status": destination.status,
        "validation_method": destination.validation_method,
        "validation_reason_code": destination.validation_reason_code,
        "is_active": bool(destination.is_active),
        "is_default": bool(destination.is_default),
        "effective_at": (
            destination.effective_at.isoformat()
            if destination.effective_at is not None
            else None
        ),
        "expires_at": (
            destination.expires_at.isoformat()
            if destination.expires_at is not None
            else None
        ),
    }


def _state_digest(state: dict[str, Any] | None) -> str | None:
    if state is None:
        return None
    canonical = json.dumps(
        state,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _result(
    destination: AdminMarketPaymentDestination,
    reason_code: str,
) -> PaymentDestinationAdministrationResult:
    return PaymentDestinationAdministrationResult(
        destination_id=destination.id,
        destination_ref=destination.destination_ref,
        status=PaymentDestinationStatus(destination.status),
        is_active=bool(destination.is_active),
        is_default=bool(destination.is_default),
        reason_code=reason_code,
    )


__all__ = [
    "PaymentDestinationAdministrationResult",
    "PaymentDestinationAdministrationService",
]
