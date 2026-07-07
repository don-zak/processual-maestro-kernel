"""Lemon Squeezy billing integration — webhooks, checkout, portal, licenses."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from processual_api.billing.subscription_catalog import public_subscription_catalog

from ..auth.security import get_current_user
from ..services.discord_service import DiscordService

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

router = APIRouter(prefix="/billing", tags=["billing"])


# ─── Helpers ───

def _get_api_key() -> str:
    return os.environ.get("LEMONSQUEEZY_API_KEY", "")


def _get_store_id() -> str:
    return os.environ.get("LEMONSQUEEZY_STORE_ID", "")


def _get_webhook_secret() -> str:
    return os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")


def _get_success_url() -> str:
    return os.environ.get("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "https://yourdomain.com/console")


def _get_cancel_url() -> str:
    return os.environ.get("LEMONSQUEEZY_CHECKOUT_CANCEL_URL", "https://yourdomain.com/pricing")


def _load_checkouts() -> list[dict]:
    path = _DATA_DIR / "checkouts.json"
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_checkouts(data: list[dict]):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    (_DATA_DIR / "checkouts.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def _load_subscriptions() -> list[dict]:
    path = _DATA_DIR / "subscriptions.json"
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_subscriptions(data: list[dict]):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    (_DATA_DIR / "subscriptions.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), "utf-8")


def _discord() -> DiscordService:
    return DiscordService()


# ─── Variant IDs (set these in env or update here) ───

_VARIANTS = {
    "starter": os.environ.get("LS_VARIANT_STARTER", ""),
    "starter_yearly": os.environ.get("LS_VARIANT_STARTER_YEARLY", ""),
    "professional": os.environ.get("LS_VARIANT_PROFESSIONAL", ""),
    "professional_yearly": os.environ.get("LS_VARIANT_PROFESSIONAL_YEARLY", ""),
    "enterprise": os.environ.get("LS_VARIANT_ENTERPRISE", ""),
    "enterprise_yearly": os.environ.get("LS_VARIANT_ENTERPRISE_YEARLY", ""),
}


# ─── Endpoints ───

@router.post("/checkout", response_model=dict)
async def create_checkout(body: dict, current_user: dict = Depends(get_current_user)):
    """Create a Lemon Squeezy checkout session and return the URL."""
    api_key = _get_api_key()
    store_id = _get_store_id()
    if not api_key or not store_id:
        raise HTTPException(
            status_code=501,
            detail="Lemon Squeezy not configured. Set LEMONSQUEEZY_API_KEY and STORE_ID.",
        )

    variant_id = body.get("variant_id", "")
    if not variant_id:
        plan = body.get("plan", "professional")
        billing = body.get("billing", "monthly")
        variant_key = f"{plan}_yearly" if billing == "yearly" else plan
        variant_id = _VARIANTS.get(variant_key, "")
        if not variant_id:
            raise HTTPException(status_code=400, detail=f"No variant ID configured for {variant_key}")

    user_id = current_user.get("sub", "unknown")
    email = body.get("email", "")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            payload: dict[str, Any] = {
                "data": {
                    "type": "checkouts",
                    "attributes": {
                        "store_id": int(store_id),
                        "variant_id": int(variant_id),
                        "success_url": _get_success_url(),
                        "cancel_url": _get_cancel_url(),
                        "custom_data": {"user_id": user_id},
                    },
                },
            }
            if email:
                payload["data"]["attributes"]["customer_email"] = email  # type: ignore[index]

            res = await client.post(
                "https://api.lemonsqueezy.com/v1/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/vnd.api+json",
                },
            )

            if res.status_code not in (200, 201):
                return {
                    "error": f"Lemon Squeezy error: HTTP {res.status_code}",
                    "detail": "Payment provider request failed",
                }

            data = res.json()
            checkout_url = data.get("data", {}).get("attributes", {}).get("url", "")
            checkout_id = data.get("data", {}).get("id", "")

            checkouts = _load_checkouts()
            checkouts.append({
                "id": checkout_id,
                "user_id": user_id,
                "url": checkout_url,
                "variant_id": variant_id,
                "created_at": datetime.now(UTC).isoformat(),
                "completed": False,
            })
            _save_checkouts(checkouts)

            return {"url": checkout_url, "checkout_id": checkout_id}

    except ImportError:
        raise HTTPException(status_code=501, detail="httpx not installed")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:200])


@router.get("/portal", response_model=dict)
async def customer_portal(current_user: dict = Depends(get_current_user)):
    """Return the Lemon Squeezy Customer Portal URL for subscription management."""
    api_key = _get_api_key()
    if not api_key:
        raise HTTPException(status_code=501, detail="Lemon Squeezy not configured")

    user_id = current_user.get("sub", "unknown")

    subs = _load_subscriptions()
    user_subs = [s for s in subs if s.get("user_id") == user_id]
    if not user_subs:
        raise HTTPException(status_code=404, detail="No active subscription found")

    customer_id = user_subs[0].get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=404, detail="No customer ID found")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                f"https://api.lemonsqueezy.com/v1/customers/{customer_id}",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if res.status_code != 200:
                return {"error": f"Could not fetch customer: HTTP {res.status_code}"}

            return {
                "portal_url": f"https://app.lemonsqueezy.com/customers/{customer_id}",
                "customer_id": customer_id,
            }
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)[:200])


@router.post("/webhook")
async def lemon_squeezy_webhook(request: Request):
    """Handle Lemon Squeezy webhook events (order_created, subscription_*, license_key_*)."""
    secret = _get_webhook_secret()
    body = await request.body()
    raw = body.decode("utf-8")

    if secret:
        signature = request.headers.get("X-Signature", "")
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    event_name = event.get("meta", {}).get("event_name", "unknown")
    data = event.get("data", {})
    attrs = data.get("attributes", {})

    subs = _load_subscriptions()
    user_id = attrs.get("custom_data", {}).get("user_id", "unknown")

    if event_name == "order_created":
        order_id = data.get("id")
        customer_id = attrs.get("customer_id")
        first_sub = attrs.get("first_subscription", {})
        variant_id = str(first_sub.get("variant_id", "")) if first_sub else ""
        status = first_sub.get("status", "active") if first_sub else "active"
        renews_at = first_sub.get("renews_at") if first_sub else None

        subs.append({
            "id": data.get("id"),
            "user_id": user_id,
            "customer_id": str(customer_id) if customer_id else "",
            "order_id": str(order_id) if order_id else "",
            "variant_id": variant_id,
            "status": status,
            "created_at": attrs.get("created_at", ""),
            "renews_at": renews_at,
            "plan": _variant_to_plan(variant_id),
        })
        _save_subscriptions(subs)

        await _discord().send_billing_alert(
            "order_created", user_id,
            {"plan": _variant_to_plan(variant_id), "status": status},
        )

    elif event_name == "subscription_updated":
        sub_id = data.get("id")
        for s in subs:
            if s.get("id") == sub_id or s.get("order_id") == str(attrs.get("order_id", "")):
                s["status"] = attrs.get("status", s.get("status"))
                s["renews_at"] = attrs.get("renews_at", s.get("renews_at"))
                s["variant_id"] = str(attrs.get("variant_id", s.get("variant_id")))
                s["plan"] = _variant_to_plan(s["variant_id"])
                break
        _save_subscriptions(subs)

    elif event_name == "subscription_payment_failed":
        sub_id = data.get("id")
        now = datetime.now(UTC).isoformat()
        for s in subs:
            if s.get("id") == sub_id or s.get("order_id") == str(attrs.get("order_id", "")):
                s["status"] = "past_due"
                if not s.get("suspended_at"):
                    s["suspended_at"] = now
                s["stage"] = "grace"
                s["payment_failures"] = s.get("payment_failures", 0) + 1
                break
        _save_subscriptions(subs)
        await _discord().send_billing_alert(
            "subscription_payment_failed", user_id,
            {"stage": "grace", "payment_failures": str(s.get("payment_failures", 1))},
        )

    elif event_name == "subscription_cancelled":
        sub_id = data.get("id")
        for s in subs:
            if s.get("id") == sub_id or s.get("order_id") == str(attrs.get("order_id", "")):
                s["status"] = "cancelled"
                s["cancelled_at"] = attrs.get("cancelled_at", "")
                break
        _save_subscriptions(subs)
        await _discord().send_billing_alert("subscription_cancelled", user_id)

    elif event_name == "subscription_expired":
        sub_id = data.get("id")
        for s in subs:
            if s.get("id") == sub_id:
                s["status"] = "expired"
                break
        _save_subscriptions(subs)

    return {"received": True, "event": event_name}


@router.get("/subscription", response_model=dict)
async def get_billing_subscription(current_user: dict = Depends(get_current_user)):
    """Get the current user's subscription info."""
    user_id = current_user.get("sub", "unknown")
    subs = _load_subscriptions()
    user_subs = [s for s in subs if s.get("user_id") == user_id]
    if not user_subs:
        return {
            "plan": "demo",
            "status": "active",
            "billing_provider": "lemonsqueezy",
            "has_subscription": False,
        }

    latest = max(user_subs, key=lambda s: s.get("created_at", ""))
    return {
        "plan": latest.get("plan", "unknown"),
        "status": latest.get("status", "unknown"),
        "renews_at": latest.get("renews_at"),
        "customer_id": latest.get("customer_id"),
        "billing_provider": "lemonsqueezy",
        "has_subscription": True,
    }


# ─── Helpers ───

def _variant_to_plan(variant_id: str) -> str:
    mapping = {}
    for plan, vid in _VARIANTS.items():
        if vid and str(vid) == str(variant_id):
            mapping[str(vid)] = plan.replace("_yearly", "")
    return mapping.get(str(variant_id), "unknown")


@router.get("/pricing-catalog")
async def get_pricing_catalog() -> dict[str, object]:
    """Return the public-safe draft subscription pricing catalog."""
    return public_subscription_catalog()
