from __future__ import annotations

import inspect
import sys
from collections import Counter

from fastapi.routing import APIRoute


_REQUIRED_ROUTES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("POST", "/billing/webhook"),
    ("POST", "/admin-marketplace/subscriptions/usage"),
}


def evaluate_staging_routes(app) -> tuple[str, ...]:
    route_counts: Counter[tuple[str, str]] = Counter()
    route_endpoints: dict[tuple[str, str], object] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            key = (method, route.path)
            route_counts[key] += 1
            route_endpoints[key] = route.endpoint

    missing = sorted(_REQUIRED_ROUTES - set(route_counts))
    if missing:
        raise RuntimeError(f"staging smoke: required routes are missing: {missing}")

    duplicates = sorted(key for key in _REQUIRED_ROUTES if route_counts[key] != 1)
    if duplicates:
        raise RuntimeError(f"staging smoke: required routes are duplicated: {duplicates}")

    webhook = route_endpoints[("POST", "/billing/webhook")]
    webhook_source = inspect.getsource(webhook)
    if "ingest_lemon_squeezy_webhook_request_factory" not in webhook_source:
        raise RuntimeError("staging smoke: secure webhook ingestion is not installed")
    if "_save_subscriptions" in webhook_source or "send_billing_alert" in webhook_source:
        raise RuntimeError("staging smoke: legacy webhook side effects are installed")

    usage = route_endpoints[("POST", "/admin-marketplace/subscriptions/usage")]
    usage_source = inspect.getsource(usage)
    if "record_subscription_usage_factory" not in usage_source:
        raise RuntimeError("staging smoke: atomic usage service is not installed")
    if "customer_ref" in getattr(usage, "__annotations__", {}):
        raise RuntimeError("staging smoke: usage endpoint accepts external customer binding")

    from processual_api.middleware import subscription as subscription_middleware

    middleware_source = inspect.getsource(subscription_middleware)
    if "subscriptions.json" in middleware_source or "_load_subscriptions" in middleware_source:
        raise RuntimeError("staging smoke: legacy subscription JSON fallback is installed")

    return tuple(sorted(f"{method} {path}" for method, path in _REQUIRED_ROUTES))


def main() -> int:
    try:
        from processual_api.main import app

        routes = evaluate_staging_routes(app)
    except Exception as exc:
        print(f"staging smoke failed: {exc}", file=sys.stderr)
        return 1
    print("staging smoke passed: " + ", ".join(routes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
