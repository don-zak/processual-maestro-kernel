from __future__ import annotations

import asyncio
import getpass
import os
import sys

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

SECRET_HASH_ENV = (
    "AUTH_PLATFORM_ADMIN_BOOTSTRAP_SECRET_SHA256"
)


def _required_prompt(label: str) -> str:
    value = input(label).strip()
    if not value:
        raise ValueError(
            f"{label.strip(': ')} is required."
        )
    return value


def _password_prompt() -> str:
    password = getpass.getpass(
        "Platform administrator password: "
    )
    confirmation = getpass.getpass(
        "Confirm platform administrator password: "
    )
    if password != confirmation:
        raise ValueError(
            "Password confirmation does not match."
        )
    return password


async def _run() -> int:
    expected_secret_sha256 = os.environ.get(
        SECRET_HASH_ENV,
        "",
    ).strip()

    if not expected_secret_sha256:
        print(
            f"{SECRET_HASH_ENV} is required.",
            file=sys.stderr,
        )
        return 2

    email = _required_prompt(
        "Platform administrator email: "
    )
    display_name = _required_prompt(
        "Platform administrator display name: "
    )
    password = _password_prompt()
    bootstrap_secret = getpass.getpass(
        "One-time bootstrap secret: "
    )

    service = PlatformAdminBootstrapService(
        unit_of_work_factory=lambda: (
            SqlAlchemyPlatformAdminBootstrapUnitOfWork(
                get_session_factory()
            )
        ),
        password_service=PasswordService(),
        expected_secret_sha256=(
            expected_secret_sha256
        ),
    )

    try:
        receipt = await service.bootstrap(
            PlatformAdminBootstrapCommand(
                email=email,
                display_name=display_name,
                password=password,
                bootstrap_secret=bootstrap_secret,
            )
        )
    except PlatformAdminBootstrapDeniedError:
        print(
            "Platform administrator bootstrap denied.",
            file=sys.stderr,
        )
        return 3
    except PlatformAdminAlreadyBootstrappedError:
        print(
            "Platform administrator bootstrap "
            "is already closed.",
            file=sys.stderr,
        )
        return 4
    except PlatformAdminBootstrapEmailConflictError:
        print(
            "Bootstrap identity email is unavailable.",
            file=sys.stderr,
        )
        return 5
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 6

    print("PlatformAdminBootstrapCreated=True")
    print(f"PlatformAdminUserId={receipt.user_id}")
    print(
        "PlatformAdminEmail="
        f"{receipt.email_normalized}"
    )
    print(
        "PlatformAdminAuthority="
        f"{receipt.authority}"
    )
    print(
        "PlatformAdminMfaRequired="
        f"{receipt.mfa_required}"
    )
    print(
        "PlatformAdminSessionIssued="
        f"{receipt.session_issued}"
    )
    print(
        "NextAction=login_and_complete_mfa"
    )
    return 0


def main() -> int:
    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print(
            "Platform administrator bootstrap cancelled.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
