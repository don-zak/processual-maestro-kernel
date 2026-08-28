from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_MIN_SECRET_LENGTH = 32
_MAX_FX_TTL_SECONDS = 86_400


@dataclass(frozen=True, slots=True)
class TopUpProductionReadiness:
    lemon_purchase_enabled: bool
    local_purchase_enabled: bool
    local_admin_enabled: bool
    lemon_ready: bool
    local_ready: bool
    activation_safe: bool
    blockers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "lemon_purchase_enabled": self.lemon_purchase_enabled,
            "local_purchase_enabled": self.local_purchase_enabled,
            "local_admin_enabled": self.local_admin_enabled,
            "lemon_ready": self.lemon_ready,
            "local_ready": self.local_ready,
            "activation_safe": self.activation_safe,
            "blockers": list(self.blockers),
        }


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE_VALUES


def _positive_identifier(name: str) -> bool:
    value = os.environ.get(name, "").strip()
    return value.isdecimal() and int(value) > 0


def _https_url(name: str) -> bool:
    value = os.environ.get(name, "").strip()
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _positive_decimal(name: str) -> bool:
    value = os.environ.get(name, "").strip()
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        return False
    return parsed.is_finite() and parsed > 0


def _bounded_positive_int(name: str, *, maximum: int) -> bool:
    value = os.environ.get(name, "").strip()
    try:
        parsed = int(value)
    except ValueError:
        return False
    return 0 < parsed <= maximum


def _aware_iso8601(name: str) -> bool:
    value = os.environ.get(name, "").strip()
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def evaluate_top_up_production_readiness() -> TopUpProductionReadiness:
    lemon_enabled = _enabled("MAESTRO_TOP_UP_PURCHASE_ENABLED")
    local_enabled = _enabled("MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED")
    local_admin_enabled = _enabled("MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED")
    blockers: list[str] = []

    lemon_requirements = {
        "lemon_api_key_missing": bool(os.environ.get("LEMONSQUEEZY_API_KEY", "").strip()),
        "lemon_store_id_invalid": _positive_identifier("LEMONSQUEEZY_STORE_ID"),
        "lemon_top_up_variant_invalid": _positive_identifier("LEMONSQUEEZY_TOP_UP_VARIANT_ID"),
        "lemon_webhook_secret_weak": len(os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "").strip())
        >= _MIN_SECRET_LENGTH,
        "lemon_success_url_invalid": _https_url("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL"),
    }
    lemon_ready = all(lemon_requirements.values())
    if lemon_enabled:
        blockers.extend(code for code, ok in lemon_requirements.items() if not ok)

    local_requirements = {
        "tunisia_fx_rate_invalid": _positive_decimal("MAESTRO_TUNISIA_USD_TND_RATE"),
        "tunisia_fx_source_missing": bool(os.environ.get("MAESTRO_TUNISIA_FX_SOURCE", "").strip()),
        "tunisia_fx_reference_missing": bool(os.environ.get("MAESTRO_TUNISIA_FX_REFERENCE", "").strip()),
        "tunisia_fx_ttl_invalid": _bounded_positive_int(
            "MAESTRO_TUNISIA_FX_TTL_SECONDS",
            maximum=_MAX_FX_TTL_SECONDS,
        ),
        "tunisia_fx_observed_at_invalid": _aware_iso8601("MAESTRO_TUNISIA_FX_OBSERVED_AT"),
    }
    local_ready = all(local_requirements.values())
    if local_enabled or local_admin_enabled:
        blockers.extend(code for code, ok in local_requirements.items() if not ok)
    if local_enabled and not local_admin_enabled:
        blockers.append("tunisia_admin_verification_disabled")
    if local_admin_enabled and not local_enabled:
        blockers.append("tunisia_purchase_disabled")

    return TopUpProductionReadiness(
        lemon_purchase_enabled=lemon_enabled,
        local_purchase_enabled=local_enabled,
        local_admin_enabled=local_admin_enabled,
        lemon_ready=lemon_ready,
        local_ready=local_ready,
        activation_safe=not blockers,
        blockers=tuple(sorted(set(blockers))),
    )


def require_top_up_production_readiness() -> TopUpProductionReadiness:
    readiness = evaluate_top_up_production_readiness()
    if not readiness.activation_safe:
        raise RuntimeError(
            "Top-up production activation is blocked by incomplete or inconsistent configuration."
        )
    return readiness


__all__ = [
    "TopUpProductionReadiness",
    "evaluate_top_up_production_readiness",
    "require_top_up_production_readiness",
]
