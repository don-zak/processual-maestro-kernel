from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass

from processual_api.auth.passwords import PasswordService
from processual_api.auth.platform_admin_bootstrap_repository import (
    SqlAlchemyPlatformAdminBootstrapUnitOfWork,
)
from processual_api.auth.platform_admin_bootstrap_service import (
    PlatformAdminAlreadyBootstrappedError,
    PlatformAdminBootstrapCommand,
    PlatformAdminBootstrapDeniedError,
    PlatformAdminBootstrapEmailConflictError,
    PlatformAdminBootstrapService,
)
from processual_api.db.session import get_session_factory

SECRET_HASH_ENV = "AUTH_PLATFORM_ADMIN_BOOTSTRAP_SECRET_SHA256"
SECRET_ENV = "AUTH_PLATFORM_ADMIN_BOOTSTRAP_SECRET"
DISPLAY_NAME_ENV = "MAESTRO_ADMIN_DISPLAY_NAME"
EMAIL_ENV = "MAESTRO_ADMIN_EMAIL"
PASSWORD_ENV = "MAESTRO_ADMIN_PASSWORD"
DEFAULT_DISPLAY_NAME = "Processual Maestro Platform Admin"


@dataclass(frozen=True, slots=True)
class BootstrapEnvironment:
    email: str
    display_name: str
    password: str
    bootstrap_secret: str
    expected_secret_sha256: str


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required for first platform-admin bootstrap.")
    return value


def _load_environment() -> BootstrapEnvironment:
    return BootstrapEnvironment(
        email=_required(EMAIL_ENV),
        display_name=os.environ.get(DISPLAY_NAME_ENV, DEFAULT_DISPLAY_NAME).strip()
        or DEFAULT_DISPLAY_NAME,
        password=_required(PASSWORD_ENV),
        bootstrap_secret=_required(SECRET_ENV),
        expected_secret_sha256=_required(SECRET_HASH_ENV),
    )


async def _platform_admin_authority_exists() -> bool:
    async with SqlAlchemyPlatformAdminBootstrapUnitOfWork(
        get_session_factory()
    ) as unit:
        repository = unit.repository
        if repository is None:
            raise RuntimeError("Platform-admin bootstrap repository is unavailable.")
        return await repository.platform_admin_authority_exists()


async def _bootstrap(environment: BootstrapEnvironment) -> None:
    service = PlatformAdminBootstrapService(
        unit_of_work_factory=lambda: SqlAlchemyPlatformAdminBootstrapUnitOfWork(
            get_session_factory()
        ),
        password_service=PasswordService(),
        expected_secret_sha256=environment.expected_secret_sha256,
    )
    await service.bootstrap(
        PlatformAdminBootstrapCommand(
            email=environment.email,
            display_name=environment.display_name,
            password=environment.password,
            bootstrap_secret=environment.bootstrap_secret,
        )
    )


async def _run() -> int:
    try:
        if await _platform_admin_authority_exists():
            print("PlatformAdminBootstrapClosed=True")
            return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        environment = _load_environment()
        await _bootstrap(environment)
    except PlatformAdminAlreadyBootstrappedError:
        print("PlatformAdminBootstrapClosed=True")
        return 0
    except PlatformAdminBootstrapDeniedError:
        print("Platform administrator bootstrap denied.", file=sys.stderr)
        return 3
    except PlatformAdminBootstrapEmailConflictError:
        print("Bootstrap identity email is unavailable.", file=sys.stderr)
        return 4
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 5

    print("PlatformAdminBootstrapCreated=True")
    print("NextAction=login_and_complete_mfa")
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print("Platform administrator bootstrap cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
