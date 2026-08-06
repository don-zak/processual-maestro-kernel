from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from processual_api.admin_marketplace.errors import AdminMarketplaceError

_MAX_BODY_BYTES = 1_048_576
_SIGNATURE_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SUPPORTED_EVENTS = frozenset(
    {
        "order_created",
        "order_refunded",
        "subscription_created",
        "subscription_updated",
        "subscription_cancelled",
        "subscription_resumed",
        "subscription_expired",
        "subscription_paused",
        "subscription_unpaused",
        "subscription_payment_failed",
        "subscription_payment_success",
        "subscription_payment_recovered",
        "subscription_payment_refunded",
    }
)
_REQUIRED_CUSTOM_REFERENCES = (
    "customer_ref",
    "order_ref",
    "offer_ref",
)


class LemonSqueezyWebhookError(AdminMarketplaceError):
    """Fail-closed error for an untrusted or malformed webhook request."""


def _reject_duplicate_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LemonSqueezyWebhookError("webhook JSON contains duplicate keys.")
        result[key] = value
    return result


def _required_mapping(
    value: object,
    *,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise LemonSqueezyWebhookError(f"{field_name} must be an object.")
    return value


def _required_text(
    value: object,
    *,
    field_name: str,
    maximum: int = 128,
) -> str:
    if not isinstance(value, str):
        raise LemonSqueezyWebhookError(f"{field_name} must be text.")
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise LemonSqueezyWebhookError(f"{field_name} is invalid.")
    return normalized


def _positive_identifier(value: object, *, field_name: str) -> str:
    if isinstance(value, bool):
        raise LemonSqueezyWebhookError(f"{field_name} is invalid.")
    if isinstance(value, int):
        if value <= 0:
            raise LemonSqueezyWebhookError(f"{field_name} is invalid.")
        return str(value)
    normalized = _required_text(value, field_name=field_name)
    if not normalized.isdecimal() or int(normalized) <= 0:
        raise LemonSqueezyWebhookError(f"{field_name} is invalid.")
    return normalized


def _internal_reference(value: object, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name)
    if not _REFERENCE_PATTERN.fullmatch(normalized):
        raise LemonSqueezyWebhookError(f"{field_name} is invalid.")
    return normalized


def verify_lemon_squeezy_signature(
    *,
    raw_body: bytes,
    signature: str,
    signing_secret: str,
) -> None:
    if not isinstance(raw_body, bytes) or not raw_body:
        raise LemonSqueezyWebhookError("webhook body is required.")
    if len(raw_body) > _MAX_BODY_BYTES:
        raise LemonSqueezyWebhookError("webhook body is too large.")

    secret = _required_text(
        signing_secret,
        field_name="webhook signing secret",
        maximum=512,
    )
    candidate = _required_text(
        signature,
        field_name="X-Signature",
        maximum=64,
    )
    if not _SIGNATURE_PATTERN.fullmatch(candidate):
        raise LemonSqueezyWebhookError("X-Signature is invalid.")

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, candidate.lower()):
        raise LemonSqueezyWebhookError("webhook signature verification failed.")


@dataclass(frozen=True, slots=True)
class VerifiedLemonSqueezyWebhook:
    event_name: str
    resource_type: str
    external_resource_id: str
    store_id: str
    customer_ref: str
    order_ref: str
    offer_ref: str
    test_mode: bool
    payload: Mapping[str, Any]


def parse_verified_lemon_squeezy_webhook(
    *,
    raw_body: bytes,
    signature: str,
    signing_secret: str,
    event_header: str,
    expected_store_id: str,
) -> VerifiedLemonSqueezyWebhook:
    verify_lemon_squeezy_signature(
        raw_body=raw_body,
        signature=signature,
        signing_secret=signing_secret,
    )

    try:
        decoded = raw_body.decode("utf-8", errors="strict")
        payload = json.loads(decoded, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LemonSqueezyWebhookError("webhook body must be valid UTF-8 JSON.") from exc

    root = _required_mapping(payload, field_name="webhook body")
    meta = _required_mapping(root.get("meta"), field_name="meta")
    data = _required_mapping(root.get("data"), field_name="data")
    attributes = _required_mapping(data.get("attributes"), field_name="data.attributes")

    header_event = _required_text(event_header, field_name="X-Event-Name").lower()
    payload_event = _required_text(meta.get("event_name"), field_name="meta.event_name").lower()
    if header_event != payload_event:
        raise LemonSqueezyWebhookError("webhook event names do not match.")
    if payload_event not in _SUPPORTED_EVENTS:
        raise LemonSqueezyWebhookError("webhook event is not supported.")

    store_id = _positive_identifier(
        attributes.get("store_id"),
        field_name="data.attributes.store_id",
    )
    trusted_store_id = _positive_identifier(
        expected_store_id,
        field_name="expected_store_id",
    )
    if store_id != trusted_store_id:
        raise LemonSqueezyWebhookError("webhook store does not match the configured store.")

    resource_type = _required_text(data.get("type"), field_name="data.type").lower()
    external_resource_id = _positive_identifier(data.get("id"), field_name="data.id")

    custom_data = _required_mapping(meta.get("custom_data"), field_name="meta.custom_data")
    references = {
        name: _internal_reference(
            custom_data.get(name),
            field_name=f"meta.custom_data.{name}",
        )
        for name in _REQUIRED_CUSTOM_REFERENCES
    }

    test_mode = attributes.get("test_mode")
    if not isinstance(test_mode, bool):
        raise LemonSqueezyWebhookError("data.attributes.test_mode must be boolean.")

    return VerifiedLemonSqueezyWebhook(
        event_name=payload_event,
        resource_type=resource_type,
        external_resource_id=external_resource_id,
        store_id=store_id,
        customer_ref=references["customer_ref"],
        order_ref=references["order_ref"],
        offer_ref=references["offer_ref"],
        test_mode=test_mode,
        payload=MappingProxyType(dict(root)),
    )
