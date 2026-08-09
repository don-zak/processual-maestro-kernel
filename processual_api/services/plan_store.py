"""Transitional API-key plan policy bridge.

Historical pilot policies remain available for legacy API keys. Current
commercial plan identifiers are bound to the authoritative fulfillment catalog
so counted API-key requests cannot silently fall back to Pilot Starter quotas.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_SPECS,
    normalize_plan_code,
)

DEFAULT_API_PLAN_ID = "pilot_starter"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _authoritative_policy(plan_code: str) -> dict[str, Any]:
    spec = PLAN_FULFILLMENT_SPECS[plan_code]
    return {
        "id": spec.plan_code,
        "name": spec.plan_code.replace("_", " ").title(),
        "source": "authoritative_fulfillment_catalog",
        "quotas": {
            "evaluation": spec.monthly_unit_allowance,
        },
    }


PLAN_POLICIES: dict[str, dict[str, Any]] = {
    "pilot_starter": {
        "id": "pilot_starter",
        "name": "Pilot Starter",
        "source": "legacy_plan",
        "quotas": {
            "evaluation": 50,
        },
    },
    "pilot_pro": {
        "id": "pilot_pro",
        "name": "Pilot Pro",
        "source": "legacy_plan",
        "quotas": {
            "evaluation": 500,
        },
    },
    "institution_trial": {
        "id": "institution_trial",
        "name": "Institution Trial",
        "source": "legacy_plan",
        "quotas": {
            "evaluation": 2000,
        },
    },
    "enterprise_private": {
        "id": "enterprise_private",
        "name": "Enterprise Private",
        "source": "legacy_plan",
        "quotas": {
            # -1 means unlimited in the current quota_store logic.
            "evaluation": _env_int("PMK_ENTERPRISE_PRIVATE_EVALUATION_QUOTA", -1),
        },
    },
    **{
        plan_code: _authoritative_policy(plan_code)
        for plan_code in PLAN_FULFILLMENT_SPECS
    },
}


PLAN_ALIASES: dict[str, str] = {
    "pilot": "pilot_starter",
    "pilot_starter": "pilot_starter",
    "pilotstarter": "pilot_starter",
    "pro": "pilot_pro",
    "pilot_pro": "pilot_pro",
    "pilotpro": "pilot_pro",
    "institution": "institution_trial",
    "institution_trial": "institution_trial",
    "institutiontrial": "institution_trial",
    "trial": "institution_trial",
    "enterprise_private": "enterprise_private",
    "enterpriseprivate": "enterprise_private",
    "enterprise": "enterprise_pilot",
    "enterprise_integration": "enterprise_pilot",
}


def normalize_plan_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("-", "_").replace(" ", "_")
    return text


def resolve_plan_id(value: Any) -> str:
    normalized = normalize_plan_key(value)
    if not normalized:
        return DEFAULT_API_PLAN_ID

    if normalized in PLAN_POLICIES:
        return normalized

    compact = normalized.replace("_", "")
    alias = PLAN_ALIASES.get(normalized) or PLAN_ALIASES.get(compact)
    if alias is not None:
        return alias

    canonical = normalize_plan_code(normalized)
    if canonical in PLAN_POLICIES:
        return canonical

    raise KeyError(f"unknown API quota plan: {normalized}")


def get_plan_policy(plan_id: Any) -> dict[str, Any]:
    resolved = resolve_plan_id(plan_id)
    return deepcopy(PLAN_POLICIES[resolved])


def quota_limit_for_plan(
    plan_id: Any,
    quota_scope: str = "evaluation",
    default: int = 50,
) -> int:
    policy = get_plan_policy(plan_id)
    quotas = policy.get("quotas", {})

    try:
        return int(quotas.get(quota_scope, quotas.get("evaluation", default)))
    except (TypeError, ValueError):
        return default
