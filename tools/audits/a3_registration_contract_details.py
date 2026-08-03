from __future__ import annotations

import json
import os

os.environ.setdefault(
    "JWT_SECRET",
    "a3-ui-local-audit-only-secret-2026-not-for-production-0123456789",
)

from processual_api.main import app

TARGETS = (
    "RegistrationConfigResponseContract",
    "IndividualRegistrationRequestContract",
    "OrganizationRegistrationRequestContract",
    "RegistrationAcceptedResponseContract",
    "EmailVerificationRequestContract",
    "EmailVerificationProcessedResponseContract",
    "EmailVerificationResendRequestContract",
    "EmailVerificationResendAcceptedResponseContract",
)


def main() -> None:
    document = app.openapi()
    schemas = document.get("components", {}).get("schemas", {})

    for name in TARGETS:
        print("=" * 88)
        print(name)
        print("=" * 88)

        schema = schemas.get(name)
        if schema is None:
            print("NOT FOUND")
            continue

        print(json.dumps(schema, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
