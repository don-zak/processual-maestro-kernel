from __future__ import annotations

from typing import Any

from processual_api.billing.usage_pricing import (
    BILLING_POLICY,
    PRICING_VERSION,
    PROVIDER_COST_INCLUDED,
    monthly_unit_allowance,
    normalize_plan_id,
)

_APPROVED_PLAN_STATUSES = {"approved", "completed"}
_CLOSED_REQUEST_STATUSES = {"completed", "rejected", "cancelled", "expired"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _candidate_plan(record: dict[str, Any]) -> str:
    for key in (
        "plan_id",
        "requested_plan",
        "plan",
        "tier",
        "subscription_plan",
        "billing_plan",
    ):
        value = _text(record.get(key))
        if value:
            return value
    return ""


def _known_plan(value: str) -> str:
    normalized = normalize_plan_id(value)
    if normalized and monthly_unit_allowance(normalized) > 0:
        return normalized
    return ""


def resolve_client_plan(raw_settings: dict[str, Any]) -> tuple[str, str]:
    direct_records: list[dict[str, Any]] = []

    for key in ("subscription", "billing", "client", "account"):
        value = raw_settings.get(key)
        if isinstance(value, dict):
            direct_records.append(value)

    direct_records.append(raw_settings)

    for record in direct_records:
        plan_id = _known_plan(_candidate_plan(record))
        if plan_id:
            return plan_id, "settings"

    for entry in reversed(_records(raw_settings.get("client_requests"))):
        status = _text(entry.get("status")).lower()
        if status not in _APPROVED_PLAN_STATUSES:
            continue
        plan_id = _known_plan(_candidate_plan(entry))
        if plan_id:
            return plan_id, "client_requests"

    return "unknown", "missing"


def _request_summary(raw_settings: dict[str, Any]) -> dict[str, Any]:
    requests = _records(raw_settings.get("client_requests"))
    open_requests = [
        request
        for request in requests
        if _text(request.get("status")).lower() not in _CLOSED_REQUEST_STATUSES
    ]
    latest = requests[-1] if requests else {}

    return {
        "open": len(open_requests),
        "latest_status": _text(latest.get("status")) if latest else "",
    }


def _provider_summary(raw_settings: dict[str, Any]) -> dict[str, Any]:
    llm_provider = raw_settings.get("llm_provider")
    provider = llm_provider if isinstance(llm_provider, dict) else {}
    configured = bool(provider.get("configured"))

    return {
        "byok_required": BILLING_POLICY == "byok",
        "provider_cost_included": PROVIDER_COST_INCLUDED,
        "connection_status": "configured" if configured else "not_configured",
        "provider": _text(provider.get("provider")),
        "model": _text(provider.get("model")),
    }


def _int_value(payload: dict[str, Any], key: str) -> int:
    try:
        return int(payload.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _recommendations(
    *,
    plan_source: str,
    provider: dict[str, Any],
) -> list[dict[str, str]]:
    recommendations: list[dict[str, str]] = []

    if plan_source == "missing":
        recommendations.append(
            {
                "kind": "plan_missing",
                "severity": "info",
                "message": "No verified plan source is available yet.",
            }
        )

    if provider.get("connection_status") != "configured":
        recommendations.append(
            {
                "kind": "provider_not_configured",
                "severity": "info",
                "message": "BYOK provider connection is not configured yet.",
            }
        )

    return recommendations


def build_client_usage_summary(
    *,
    user_id: str,
    client_id: str,
    ledger_summary: dict[str, Any],
    raw_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a client-scoped usage and subscription summary.

    The router supplies raw_settings for the authenticated user only and a ledger
    summary already scoped to the authenticated client/api key identity.
    """

    raw = raw_settings if isinstance(raw_settings, dict) else {}
    ledger = ledger_summary if isinstance(ledger_summary, dict) else {}

    plan_id, plan_source = resolve_client_plan(raw)
    allowance = (
        monthly_unit_allowance(plan_id)
        if plan_id != "unknown" and plan_source != "missing"
        else 0
    )

    monthly_units_used = _int_value(ledger, "total_units")
    remaining = None
    usage_percent = None

    if allowance > 0:
        remaining = max(allowance - monthly_units_used, 0)
        usage_percent = round((monthly_units_used / allowance) * 100, 2)

    quota_status = _text(ledger.get("quota_status")).lower()
    near_limit = bool(usage_percent is not None and usage_percent >= 80)
    exceeded = bool(allowance > 0 and monthly_units_used >= allowance)
    if quota_status == "warning":
        near_limit = True
    if quota_status == "exhausted":
        exceeded = True

    provider = _provider_summary(raw)

    return {
        "pricing_version": PRICING_VERSION,
        "billing_policy": BILLING_POLICY,
        "client_id": client_id,
        "user_id": user_id,
        "plan": {
            "plan_id": plan_id,
            "source": plan_source,
            "monthly_unit_allowance": allowance,
        },
        "usage": {
            "monthly_units_used": monthly_units_used,
            "monthly_units_allowance": allowance,
            "monthly_units_remaining": remaining,
            "usage_percent": usage_percent,
            "ledger_events": _int_value(ledger, "total_events"),
            "latest_usage_at": _text(ledger.get("latest_usage_at")),
            "current_period": _text(ledger.get("current_period")),
        },
        "quota": {
            "near_limit": near_limit,
            "exceeded": exceeded,
            "status": quota_status or "ok",
        },
        "requests": _request_summary(raw),
        "provider": provider,
        "recommendations": _recommendations(
            plan_source=plan_source,
            provider=provider,
        ),
    }
