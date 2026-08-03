from __future__ import annotations

import os

os.environ.setdefault(
    "JWT_SECRET",
    "a3-ui-local-audit-only-secret-2026-not-for-production-0123456789",
)

from processual_api.main import app

KEYWORDS = (
    "register",
    "registration",
    "verification",
    "plan",
    "subscription",
    "billing",
    "checkout",
    "offer",
    "catalog",
    "trial",
    "entitlement",
    "quota",
)


def main() -> None:
    document = app.openapi()
    schemas = document.get("components", {}).get("schemas", {})

    matched = [name for name in sorted(schemas) if any(keyword in name.lower() for keyword in KEYWORDS)]

    for name in matched:
        print(name)

    print(f"\nTOTAL_MATCHING_SCHEMAS={len(matched)}")


if __name__ == "__main__":
    main()
