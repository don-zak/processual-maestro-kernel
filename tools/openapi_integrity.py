#!/usr/bin/env python3
"""Validate the real FastAPI application route and OpenAPI identity surface."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute

from processual_api.main import app


def _iter_effective_api_routes(
    route_collection: Sequence[Any],
    seen: set[int] | None = None,
) -> Iterator[Any]:
    """Yield direct and included API routes with their effective FastAPI context.

    FastAPI 0.141+ keeps included routers as route containers. Their
    ``effective_route_contexts()`` API applies accumulated include prefixes, so
    use it when available instead of inspecting only ``app.routes`` or walking
    ``original_router.routes`` without include context.
    """

    if seen is None:
        seen = set()
    collection_id = id(route_collection)
    if collection_id in seen:
        return
    seen.add(collection_id)

    for route in route_collection:
        if isinstance(route, APIRoute):
            yield route
            continue

        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if callable(effective_route_contexts):
            for context in effective_route_contexts():
                if isinstance(getattr(context, "original_route", None), APIRoute):
                    yield context
            continue

        nested = getattr(route, "routes", None)
        if isinstance(nested, Sequence):
            yield from _iter_effective_api_routes(nested, seen)


def audit() -> dict[str, object]:
    route_pairs: list[tuple[str, str]] = []
    for route in _iter_effective_api_routes(app.routes):
        path = str(getattr(route, "path", "") or "")
        methods = getattr(route, "methods", set()) or set()
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS"}:
                continue
            route_pairs.append((method, path))

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
