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
    "verify",
    "verification",
    "auth",
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
    paths = document.get("paths", {})

    rows: list[tuple[str, str, str]] = []

    for path, operations in paths.items():
        if not isinstance(operations, dict):
            continue

        for method, operation in operations.items():
            if method.lower() not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
            }:
                continue

            operation = operation if isinstance(operation, dict) else {}
            operation_id = str(operation.get("operationId", ""))
            summary = str(operation.get("summary", ""))
            tags = " ".join(str(tag) for tag in operation.get("tags", []))

            searchable = " ".join((path, operation_id, summary, tags)).lower()

            if any(keyword in searchable for keyword in KEYWORDS):
                rows.append(
                    (
                        method.upper(),
                        path,
                        operation_id or summary or "-",
                    )
                )

    for method, path, operation_id in sorted(rows, key=lambda row: (row[1], row[0])):
        print(f"{method:<8} {path:<76} {operation_id}")

    print(f"\nTOTAL_MATCHING_ROUTES={len(rows)}")


if __name__ == "__main__":
    main()
