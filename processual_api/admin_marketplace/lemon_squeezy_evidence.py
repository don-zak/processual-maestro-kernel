from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping


class LemonSqueezyEvidenceError(ValueError):
    """Raised when a signed payload lacks reconciliation-grade evidence."""


@dataclass(frozen=True, slots=True)
class LemonSqueezyVerifiedEvidence:
    schema_version: int
    provider_customer_id: str
    provider_order_id: str | None
    provider_subscription_id: str | None
    variant_id: str | None
    currency: str | None
    total_amount: str | None
    status: str
    effective_at: datetime

    def as_json(self) -> dict[str, object]:
        result = asdict(self)
        result["effective_at"] = self.effective_at.isoformat()
        return result


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise LemonSqueezyEvidenceError(f"{field} must be an object")
    return value


def _identifier(value: object, field: str) -> str:
    if isinstance(value, bool):
        raise LemonSqueezyEvidenceError(f"{field} is invalid")
    text = str(value).strip() if isinstance(value, (str, int)) else ""
    if not text.isdecimal() or int(text) <= 0:
        raise LemonSqueezyEvidenceError(f"{field} is invalid")
    return text


def _text(value: object, field: str, maximum: int = 64) -> str:
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > maximum:
        raise LemonSqueezyEvidenceError(f"{field} is invalid")
    return text


def _currency(value: object, field: str) -> str:
    text = _text(value, field, maximum=3).upper()
    if len(text) != 3 or not text.isalpha():
        raise LemonSqueezyEvidenceError(f"{field} is invalid")
    return text


def _amount(value: object, field: str) -> str:
    if isinstance(value, bool):
        raise LemonSqueezyEvidenceError(f"{field} is invalid")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LemonSqueezyEvidenceError(f"{field} is invalid") from exc
    if not amount.is_finite() or amount < 0:
        raise LemonSqueezyEvidenceError(f"{field} is invalid")
    return format(amount, "f")


def _timestamp(value: object, field: str) -> datetime:
    text = _text(value, field, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LemonSqueezyEvidenceError(f"{field} is invalid") from exc
    if parsed.tzinfo is None:
        raise LemonSqueezyEvidenceError(f"{field} must be timezone-aware")
    return parsed


def extract_lemon_squeezy_verified_evidence(
    *,
    resource_type: str,
    external_resource_id: str,
    attributes: Mapping[str, Any],
) -> LemonSqueezyVerifiedEvidence:
    customer_id = _identifier(attributes.get("customer_id"), "customer_id")
    status = _text(attributes.get("status"), "status")
    effective_at = _timestamp(
        attributes.get("updated_at") or attributes.get("created_at"),
        "updated_at",
    )

    if resource_type == "orders":
        first_item = _mapping(attributes.get("first_order_item"), "first_order_item")
        return LemonSqueezyVerifiedEvidence(
            schema_version=1,
            provider_customer_id=customer_id,
            provider_order_id=external_resource_id,
            provider_subscription_id=None,
            variant_id=_identifier(first_item.get("variant_id"), "variant_id"),
            currency=_currency(attributes.get("currency"), "currency"),
            total_amount=_amount(attributes.get("total"), "total"),
            status=status,
            effective_at=effective_at,
        )

    if resource_type == "subscriptions":
        return LemonSqueezyVerifiedEvidence(
            schema_version=1,
            provider_customer_id=customer_id,
            provider_order_id=_identifier(attributes.get("order_id"), "order_id"),
            provider_subscription_id=external_resource_id,
            variant_id=_identifier(attributes.get("variant_id"), "variant_id"),
            currency=None,
            total_amount=None,
            status=status,
            effective_at=effective_at,
        )

    if resource_type == "subscription-invoices":
        return LemonSqueezyVerifiedEvidence(
            schema_version=1,
            provider_customer_id=customer_id,
            provider_order_id=None,
            provider_subscription_id=_identifier(
                attributes.get("subscription_id"), "subscription_id"
            ),
            variant_id=None,
            currency=_currency(attributes.get("currency"), "currency"),
            total_amount=_amount(attributes.get("total"), "total"),
            status=status,
            effective_at=effective_at,
        )

    raise LemonSqueezyEvidenceError("resource type is not supported for evidence")


__all__ = [
    "LemonSqueezyEvidenceError",
    "LemonSqueezyVerifiedEvidence",
    "extract_lemon_squeezy_verified_evidence",
]
