import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import processual_api.billing.router as billing_router
import processual_api.middleware.subscription as subscription_module
import processual_api.routers.settings as settings_router


ROOT = Path(__file__).resolve().parents[1]


def test_billing_router_keeps_expected_public_routes_and_events():
    source = (ROOT / "processual_api" / "billing" / "router.py").read_text(
        encoding="utf-8"
    )

    required_markers = [
        'APIRouter(prefix="/billing"',
        "checkout",
        "portal",
        "webhook",
        'get("/subscription"',
        "get_billing_subscription",
        "order_created",
        "subscription_updated",
        "subscription_payment_failed",
        "subscription_cancelled",
        "subscription_expired",
        "lemonsqueezy",
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing billing router markers: {missing}"


def test_billing_subscription_store_roundtrip_uses_json_file(tmp_path, monkeypatch):
    monkeypatch.setattr(billing_router, "_DATA_DIR", tmp_path)

    records = [
        {
            "user_id": "user-1",
            "subscription_id": "sub-1",
            "plan": "professional",
            "status": "active",
            "stage": "active",
            "created_at": "2026-06-30T10:00:00+00:00",
        },
        {
            "user_id": "user-2",
            "subscription_id": "sub-2",
            "plan": "enterprise",
            "status": "past_due",
            "stage": "grace",
            "payment_failures": 1,
            "suspended_at": "2026-06-30T10:00:00+00:00",
        },
    ]

    billing_router._save_subscriptions(records)

    stored_path = tmp_path / "subscriptions.json"
    assert stored_path.is_file()
    assert json.loads(stored_path.read_text(encoding="utf-8")) == records
    assert billing_router._load_subscriptions() == records


def test_billing_subscription_returns_demo_state_when_user_has_no_subscription(
    monkeypatch,
):
    monkeypatch.setattr(billing_router, "_load_subscriptions", lambda: [])

    response = asyncio.run(
        billing_router.get_billing_subscription(
            {
                "user_id": "missing-user",
                "id": "missing-user",
                "sub": "missing-user",
                "email": "missing@example.com",
            }
        )
    )

    assert response["has_subscription"] is False
    assert response["plan"] == "demo"
    assert response["billing_provider"] == "lemonsqueezy"


def test_subscription_middleware_policy_constants_are_guarded():
    assert "GET" in subscription_module._READ_ONLY_METHODS
    assert "HEAD" in subscription_module._READ_ONLY_METHODS
    assert "OPTIONS" in subscription_module._READ_ONLY_METHODS
    assert "POST" not in subscription_module._READ_ONLY_METHODS

    assert "/billing" in subscription_module._SUSPENSION_ALLOWED_PREFIXES


def test_subscription_middleware_stage_boundaries_are_stable():
    now = datetime.now(UTC)

    assert subscription_module._compute_stage({"status": "active"}) == "active"
    assert subscription_module._compute_stage({"status": "expired"}) == "expired"
    assert subscription_module._compute_stage({"status": "cancelled"}) == "expired"

    recent_failure = {
        "status": "past_due",
        "suspended_at": (now - timedelta(days=2)).isoformat(),
    }
    assert subscription_module._compute_stage(recent_failure) == "grace"

    suspended_failure = {
        "status": "past_due",
        "suspended_at": (now - timedelta(days=30)).isoformat(),
    }
    assert subscription_module._compute_stage(suspended_failure) == "suspended"

    expired_failure = {
        "status": "past_due",
        "suspended_at": (now - timedelta(days=120)).isoformat(),
    }
    assert subscription_module._compute_stage(expired_failure) == "expired"


def test_settings_subscription_reads_billing_subscriptions_before_local_settings():
    source = (ROOT / "processual_api" / "routers" / "settings.py").read_text(
        encoding="utf-8"
    )

    required_markers = [
        "def _load_billing_subscriptions()",
        'subscriptions.json"',
        'router.get("/subscription"',
        "billing_subs = _load_billing_subscriptions()",
        'latest.get("plan"',
        'latest.get("status"',
        'latest.get("suspended_at"',
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing settings subscription markers: {missing}"


def test_billing_package_exports_billing_router_alias():
    import processual_api.billing as billing_package

    assert billing_package.billing_router is billing_router.router