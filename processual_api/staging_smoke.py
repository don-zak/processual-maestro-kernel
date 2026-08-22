from __future__ import annotations

import inspect
import sys
from collections import Counter

_REQUIRED_ROUTES = {
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("POST", "/billing/checkout"),
    ("POST", "/billing/webhook"),
    ("POST", "/admin-marketplace/subscriptions/usage"),
}


def _openapi_routes(app) -> set[tuple[str, str]]:
    schema = app.openapi()
    paths = schema.get("paths", {}) if isinstance(schema, dict) else {}
    discovered: set[tuple[str, str]] = set()
    if not isinstance(paths, dict):
        return discovered
    for path, operations in paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            continue
        for method in operations:
            normalized = str(method).upper()
            if normalized in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
                discovered.add((normalized, path))
    return discovered


def _route_counts(app) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not isinstance(path, str) or methods is None:
            continue
        for method in methods:
            counts[(str(method).upper(), path)] += 1
    return counts


def evaluate_staging_routes(app) -> tuple[str, ...]:
    mounted_routes = _openapi_routes(app)
    missing = sorted(_REQUIRED_ROUTES - mounted_routes)
    if missing:
        raise RuntimeError(f"staging smoke: required routes are missing: {missing}")

    route_counts = _route_counts(app)
    duplicates = sorted(key for key in _REQUIRED_ROUTES if route_counts[key] > 1)
    if duplicates:
        raise RuntimeError(f"staging smoke: required routes are duplicated: {duplicates}")

    from processual_api.admin_marketplace.lemon_squeezy_secure_webhook_router import (
        secure_lemon_squeezy_webhook,
    )
    from processual_api.admin_marketplace.subscription_usage_router import (
        record_subscription_usage_endpoint,
    )
    from processual_api.billing.router import create_checkout

    checkout_source = inspect.getsource(create_checkout)
    if "resolve_canonical_checkout_in_session" not in checkout_source:
        raise RuntimeError("staging smoke: canonical checkout resolution is not installed")
    if "LEMONSQUEEZY_API_KEY" not in checkout_source:
        raise RuntimeError("staging smoke: Lemon checkout provider client is not installed")

    webhook_source = inspect.getsource(secure_lemon_squeezy_webhook)
    if "ingest_lemon_squeezy_webhook_request_factory" not in webhook_source:
        raise RuntimeError("staging smoke: secure webhook ingestion is not installed")
    if "_save_subscriptions" in webhook_source or "send_billing_alert" in webhook_source:
        raise RuntimeError("staging smoke: legacy webhook side effects are installed")

    usage_source = inspect.getsource(record_subscription_usage_endpoint)
    if "record_subscription_quota_usage_factory" not in usage_source:
        raise RuntimeError("staging smoke: authoritative quota-cycle usage service is not installed")
    if "record_subscription_usage_factory" in usage_source:
        raise RuntimeError("staging smoke: legacy quota-account usage service is installed")
    if "quota_cycle_id=None" not in usage_source:
        raise RuntimeError("staging smoke: quota cycle selection is not server authoritative")
    if "customer_ref" in getattr(record_subscription_usage_endpoint, "__annotations__", {}):
        raise RuntimeError("staging smoke: usage endpoint accepts external customer binding")

    from processual_api.middleware import subscription as subscription_middleware

    middleware_source = inspect.getsource(subscription_middleware)
    if "subscriptions.json" in middleware_source or "_load_subscriptions" in middleware_source:
        raise RuntimeError("staging smoke: legacy subscription JSON fallback is installed")

    return tuple(sorted(f"{method} {path}" for method, path in _REQUIRED_ROUTES))


def main() -> int:
    try:
        from processual_api.main import app
        from processual_api.release_gate import evaluate_release_environment

        evaluate_release_environment()
        routes = evaluate_staging_routes(app)
    except Exception as exc:
        print(f"staging smoke failed: {exc}", file=sys.stderr)
        return 1
    print("staging smoke passed: " + ", ".join(routes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
