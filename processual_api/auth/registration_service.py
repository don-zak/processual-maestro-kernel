from __future__ import annotations

import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from processual_api.auth.normalization import (
    normalize_display_name,
    normalize_email,
    organization_slug,
)
from processual_api.auth.passwords import PasswordService
from processual_api.auth.registration_contracts import RegistrationMode
from processual_api.auth.registration_repository import RegistrationConflictError
from processual_api.auth.token_material import TokenDigester

EMAIL_VERIFICATION_TTL = timedelta(hours=24)
GENERIC_REGISTRATION_STATUS = "accepted"
GENERIC_NEXT_ACTION = "check_email"


class RegistrationRepository(Protocol):
    async def email_exists(self, email_normalized: str) -> bool: ...

    def add_registration(self, **values) -> None: ...


class RegistrationUnitOfWork(Protocol):
    repository: RegistrationRepository

    async def __aenter__(self) -> RegistrationUnitOfWork: ...

    async def __aexit__(self, exc_type, exc, traceback) -> None: ...

    async def commit(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RegistrationCommand:
    mode: RegistrationMode
    email: str
    display_name: str
    password: str
    accepted_terms_version: str
    organization_name: str | None = None


@dataclass(frozen=True, slots=True)
class RegistrationReceipt:
    status: str = GENERIC_REGISTRATION_STATUS
    next_action: str = GENERIC_NEXT_ACTION


@dataclass(frozen=True, slots=True)
class VerificationDelivery:
    email_normalized: str
    raw_action_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RegistrationOutcome:
    receipt: RegistrationReceipt
    delivery: VerificationDelivery | None = None


class RegistrationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], RegistrationUnitOfWork],
        password_service: PasswordService,
        token_digester: TokenDigester,
        clock: Callable[[], datetime] | None = None,
        slug_suffix_factory: Callable[[], str] | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_service = password_service
        self._token_digester = token_digester
        self._clock = clock or (lambda: datetime.now(UTC))
        self._slug_suffix_factory = slug_suffix_factory or (lambda: secrets.token_hex(4))

    async def register(self, command: RegistrationCommand) -> RegistrationOutcome:
        if command.mode not in (RegistrationMode.INDIVIDUAL, RegistrationMode.ORGANIZATION):
            raise ValueError("Registration mode is not public self-service.")
        email = normalize_email(command.email)
        display_name = normalize_display_name(command.display_name)
        terms_version = command.accepted_terms_version.strip()
        if not terms_version or len(terms_version) > 64:
            raise ValueError("accepted_terms_version is invalid.")
        organization_name = None
        slug = None
        organization_id = None
        if command.mode is RegistrationMode.ORGANIZATION:
            if command.organization_name is None:
                raise ValueError("Organization registration requires a name.")
            organization_name = normalize_display_name(command.organization_name)
            slug = organization_slug(
                organization_name,
                suffix=self._slug_suffix_factory(),
            )
            organization_id = uuid.uuid4()
        elif command.organization_name is not None:
            raise ValueError("Individual registration cannot create an organization.")

        password_hash = self._password_service.hash_password(command.password)
        verification = self._token_digester.generate_token(purpose="verify_email")
        now = self._clock()
        if now.tzinfo is None:
            raise ValueError("Registration clock must be timezone-aware.")
        expires_at = now + EMAIL_VERIFICATION_TTL
        receipt = RegistrationReceipt()

        try:
            async with self._unit_of_work_factory() as unit_of_work:
                if await unit_of_work.repository.email_exists(email):
                    return RegistrationOutcome(receipt=receipt)
                unit_of_work.repository.add_registration(
                    user_id=uuid.uuid4(),
                    email_normalized=email,
                    display_name=display_name,
                    password_hash=password_hash,
                    terms_version=terms_version,
                    accepted_at=now,
                    action_token_id=uuid.uuid4(),
                    action_token_hash=verification.digest,
                    action_token_expires_at=expires_at,
                    organization_id=organization_id,
                    organization_slug=slug,
                    organization_name=organization_name,
                )
                await unit_of_work.commit()
        except RegistrationConflictError:
            return RegistrationOutcome(receipt=receipt)

        return RegistrationOutcome(
            receipt=receipt,
            delivery=VerificationDelivery(
                email_normalized=email,
                raw_action_token=verification.raw,
                expires_at=expires_at,
            ),
        )


__all__ = [
    "RegistrationCommand",
    "RegistrationOutcome",
    "RegistrationReceipt",
    "RegistrationService",
    "RegistrationUnitOfWork",
    "VerificationDelivery",
]
