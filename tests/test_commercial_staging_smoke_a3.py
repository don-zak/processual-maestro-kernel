from __future__ import annotations

import pytest
from fastapi import FastAPI

from processual_api.staging_smoke import evaluate_staging_routes

_REQUIRED = (
    ("GET", "/health/live"),
    ("GET", "/health/ready"),
    ("POST", "/admin-marketplace/subscriptions/usage"),
    ("POST", "/billing/checkout"),
    ("POST", "/billing/webhook"),
)


def test_real_application_passes_commercial_staging_smoke() -> None:
    from processual_api.main import app

    routes = evaluate_staging_routes(app)
    assert routes == tuple(sorted(f"{method} {path}" for method, path in _REQUIRED))


def test_missing_or_duplicate_required_routes_fail_closed() -> None:
    empty = FastAPI()
    with pytest.raises(RuntimeError, match="required routes are missing"):
        evaluate_staging_routes(empty)

    duplicate = FastAPI()

    async def placeholder() -> dict[str, bool]:
        return {"ok": True}

    for method, path in _REQUIRED:
        duplicate.add_api_route(path, placeholder, methods=[method])
        duplicate.add_api_route(path, placeholder, methods=[method])

    with pytest.raises(RuntimeError, match="required routes are duplicated"):
        evaluate_staging_routes(duplicate)


def test_smoke_rejects_checkout_without_canonical_resolution(monkeypatch) -> None:
    import processual_api.staging_smoke as smoke
    from processual_api.billing.router import create_checkout
    from processual_api.main import app

    real_getsource = smoke.inspect.getsource

    def fake_getsource(value):
        if value is create_checkout:
            return 'api_key = os.getenv("LEMONSQUEEZY_API_KEY")'
        return real_getsource(value)

    monkeypatch.setattr(smoke.inspect, "getsource", fake_getsource)
    with pytest.raises(RuntimeError, match="canonical checkout resolution"):
        smoke.evaluate_staging_routes(app)


def test_smoke_rejects_legacy_webhook_side_effects(monkeypatch) -> None:
    import processual_api.staging_smoke as smoke
    from processual_api.main import app

    real_getsource = smoke.inspect.getsource

    def fake_getsource(value):
        if getattr(value, "__name__", "") == "secure_lemon_squeezy_webhook":
            return "ingest_lemon_squeezy_webhook_request_factory(); _save_subscriptions()"
        return real_getsource(value)

    monkeypatch.setattr(smoke.inspect, "getsource", fake_getsource)
    with pytest.raises(RuntimeError, match="legacy webhook side effects"):
        smoke.evaluate_staging_routes(app)


def test_smoke_rejects_subscription_json_fallback(monkeypatch) -> None:
    import processual_api.staging_smoke as smoke
    from processual_api.main import app
    from processual_api.middleware import subscription as subscription_middleware

    real_getsource = smoke.inspect.getsource

    def fake_getsource(value):
        if value is subscription_middleware:
            return "subscriptions.json"
        return real_getsource(value)

    monkeypatch.setattr(smoke.inspect, "getsource", fake_getsource)
    with pytest.raises(RuntimeError, match="legacy subscription JSON fallback"):
        smoke.evaluate_staging_routes(app)


def test_staging_smoke_main_requires_release_environment(monkeypatch, capsys) -> None:
    import processual_api.release_gate as release_gate
    import processual_api.staging_smoke as smoke

    def fail_release_environment():
        raise RuntimeError("release gate: LEMONSQUEEZY_API_KEY is required")

    monkeypatch.setattr(
        release_gate,
        "evaluate_release_environment",
        fail_release_environment,
    )

    assert smoke.main() == 1
    captured = capsys.readouterr()
    assert "LEMONSQUEEZY_API_KEY is required" in captured.err
