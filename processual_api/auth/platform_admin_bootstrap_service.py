from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from processual_api.auth.normalization import (
    normalize_display_name,
    normalize_email,
)
from processual_api.auth.passwords import PasswordService
from processual_api.auth.platform_admin_bootstrap_repository import (
    PlatformAdminBootstrapConflictError,
)


class PlatformAdminBootstrapRepository(Protocol):
    async def acquire_bootstrap_lock(self) -> None: ...

    async def platform_admin_authority_exists(
        self,
    ) -> bool: ...

    async def email_exists(
        self,
        email_normalized: str,
    ) -> bool: ...

    def add_first_platform_admin(
        self,
        **values,
    ) -> None: ...


class PlatformAdminBootstrapUnitOfWork(Protocol):
    repository: PlatformAdminBootstrapRepository

    async def __aenter__(
        self,
    ) -> PlatformAdminBootstrapUnitOfWork: ...

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None: ...

    async def commit(self) -> None: ...


class PlatformAdminBootstrapDeniedError(RuntimeError):
    """Bootstrap authorization failed."""


class PlatformAdminAlreadyBootstrappedError(RuntimeError):
    """A platform administrator has already existed."""


class PlatformAdminBootstrapEmailConflictError(RuntimeError):
    """The requested bootstrap email already exists."""


@dataclass(frozen=True, slots=True)
class PlatformAdminBootstrapCommand:
    email: str
    display_name: str
    password: str
    bootstrap_secret: str


@dataclass(frozen=True, slots=True)
class PlatformAdminBootstrapReceipt:
    user_id: uuid.UUID
    email_normalized: str
    authority: str = "platform_admin"
    mfa_required: bool = True
    session_issued: bool = False


class PlatformAdminBootstrapService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[
            [],
            PlatformAdminBootstrapUnitOfWork,
        ],
        password_service: PasswordService,
        expected_secret_sha256: str,
        clock: Callable[[], datetime] | None = None,
        user_id_factory: Callable[
            [],
            uuid.UUID,
        ] | None = None,
        authority_id_factory: Callable[
            [],
            uuid.UUID,
        ] | None = None,
    ) -> None:
        normalized_digest = (
            expected_secret_sha256.strip().lower()
        )
        if (
            len(normalized_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in normalized_digest
            )
        ):
            raise ValueError(
                "Bootstrap secret SHA-256 is invalid."
            )

        self._unit_of_work_factory = unit_of_work_factory
        self._password_service = password_service
        self._expected_secret_sha256 = normalized_digest
        self._clock = clock or (
            lambda: datetime.now(UTC)
        )
        self._user_id_factory = (
            user_id_factory or uuid.uuid4
        )
        self._authority_id_factory = (
            authority_id_factory or uuid.uuid4
        )

    def _assert_bootstrap_secret(
        self,
        bootstrap_secret: str,
    ) -> None:
        supplied_digest = hashlib.sha256(
            bootstrap_secret.encode("utf-8")
        ).hexdigest()

        if not hmac.compare_digest(
            supplied_digest,
            self._expected_secret_sha256,
        ):
            raise PlatformAdminBootstrapDeniedError(
                "Platform-admin bootstrap authorization failed."
            )

    async def bootstrap(
        self,
        command: PlatformAdminBootstrapCommand,
    ) -> PlatformAdminBootstrapReceipt:
        self._assert_bootstrap_secret(
            command.bootstrap_secret
        )

        email = normalize_email(command.email)
        display_name = normalize_display_name(
            command.display_name
        )
        password_hash = (
            self._password_service.hash_password(
                command.password
            )
        )

        now = self._clock()
        if now.tzinfo is None:
            raise ValueError(
                "Bootstrap clock must be timezone-aware."
            )

        user_id = self._user_id_factory()
        authority_id = self._authority_id_factory()

        try:
            async with self._unit_of_work_factory() as unit:
                repository = unit.repository
                if repository is None:
                    raise RuntimeError(
                        "Platform-admin bootstrap repository "
                        "is unavailable."
                    )

                await repository.acquire_bootstrap_lock()

                if (
                    await repository
                    .platform_admin_authority_exists()
                ):
                    raise (
                        PlatformAdminAlreadyBootstrappedError(
                            "Platform-admin bootstrap is closed."
                        )
                    )

                if await repository.email_exists(email):
                    raise (
                        PlatformAdminBootstrapEmailConflictError(
                            "Bootstrap identity email "
                            "already exists."
                        )
                    )

                repository.add_first_platform_admin(
                    user_id=user_id,
                    authority_id=authority_id,
                    email_normalized=email,
                    display_name=display_name,
                    password_hash=password_hash,
                    created_at=now,
                )
                await unit.commit()
        except PlatformAdminBootstrapConflictError as exc:
            raise PlatformAdminAlreadyBootstrappedError(
                "Platform-admin bootstrap is closed."
            ) from exc

        return PlatformAdminBootstrapReceipt(
            user_id=user_id,
            email_normalized=email,
        )


__all__ = [
    "PlatformAdminAlreadyBootstrappedError",
    "PlatformAdminBootstrapCommand",
    "PlatformAdminBootstrapDeniedError",
    "PlatformAdminBootstrapEmailConflictError",
    "PlatformAdminBootstrapReceipt",
    "PlatformAdminBootstrapService",
    "PlatformAdminBootstrapUnitOfWork",
]
