#!/usr/bin/env python3
"""Validate the real FastAPI application route and OpenAPI identity surface."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from fastapi.routing import APIRoute

from processual_api.main import app


def audit() -> dict[str, object]:
    route_pairs: list[tuple[str, str]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or set()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            route_pairs.append((method, route.path))

    route_counts = Counter(route_pairs)
    duplicate_routes = sorted(
        {f"{method} {path}": count for (method, path), count in route_counts.items() if count > 1}.items()
    )

    schema = app.openapi()
    operation_ids: list[str] = []
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if isinstance(operation, dict) and operation.get("operationId"):
                operation_ids.append(str(operation["operationId"]))

    operation_counts = Counter(operation_ids)
    duplicate_operation_ids = sorted(
        {key: count for key, count in operation_counts.items() if count > 1}.items()
    )

    return {
        "schema_version": 1,
        "route_pair_count": len(route_pairs),
        "operation_id_count": len(operation_ids),
        "duplicate_routes": duplicate_routes,
        "duplicate_operation_ids": duplicate_operation_ids,
        "ok": not duplicate_routes and not duplicate_operation_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    payload = audit()
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
