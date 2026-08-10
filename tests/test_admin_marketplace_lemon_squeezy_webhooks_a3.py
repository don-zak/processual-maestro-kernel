from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSqueezyWebhookError,
    parse_verified_lemon_squeezy_webhook,
    verify_lemon_squeezy_signature,
)


SECRET = "test-signing-secret"
STORE_ID = "42"


def _payload(**overrides):
    payload = {
        "meta": {
            "event_name": "subscription_created",
            "custom_data": {
                "customer_ref": "cust_123",
                "order_ref": "order_456",
                "offer_ref": "offer_pro_monthly",
            },
        },
        "data": {
            "type": "subscriptions",
            "id": "9001",
            "attributes": {
                "store_id": 42,
                "test_mode": False,
                "customer_id": 5001,
                "order_id": 6001,
                "variant_id": 8001,
                "status": "active",
                "updated_at": "2026-08-06T09:30:00Z",
            },
        },
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def _body(payload=None) -> bytes:
    return json.dumps(
        payload or _payload(),
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _signature(body: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _parse(body: bytes, **overrides):
    arguments = {
        "raw_body": body,
        "signature": _signature(body),
        "signing_secret": SECRET,
        "event_header": "subscription_created",
        "expected_store_id": STORE_ID,
    }
    arguments.update(overrides)
    return parse_verified_lemon_squeezy_webhook(**arguments)


def test_valid_webhook_is_verified_without_mutating_internal_references() -> None:
    body = _body()

    verified = _parse(body)

    assert verified.event_name == "subscription_created"
    assert verified.resource_type == "subscriptions"
    assert verified.external_resource_id == "9001"
    assert verified.store_id == STORE_ID
    assert verified.customer_ref == "cust_123"
    assert verified.order_ref == "order_456"
    assert verified.offer_ref == "offer_pro_monthly"
    assert verified.test_mode is False
    assert verified.evidence.provider_customer_id == "5001"
    assert verified.evidence.provider_order_id == "6001"
    assert verified.evidence.provider_subscription_id == "9001"
    assert verified.evidence.variant_id == "8001"


def test_signature_is_calculated_over_exact_raw_body() -> None:
    body = _body()
    altered = body.replace(b"9001", b"9002")

    with pytest.raises(LemonSqueezyWebhookError, match="signature verification failed"):
        parse_verified_lemon_squeezy_webhook(
            raw_body=altered,
            signature=_signature(body),
            signing_secret=SECRET,
            event_header="subscription_created",
            expected_store_id=STORE_ID,
        )


def test_signature_rejects_non_hex_and_wrong_length() -> None:
    body = _body()

    for signature in ("not-a-signature", "a" * 63, "g" * 64):
        with pytest.raises(LemonSqueezyWebhookError, match="X-Signature is invalid"):
            verify_lemon_squeezy_signature(
                raw_body=body,
                signature=signature,
                signing_secret=SECRET,
            )


def test_event_header_must_match_meta_event_name() -> None:
    body = _body()

    with pytest.raises(LemonSqueezyWebhookError, match="event names do not match"):
        _parse(body, event_header="subscription_cancelled")


def test_unknown_event_is_rejected_fail_closed() -> None:
    payload = _payload()
    payload["meta"]["event_name"] = "customer_created"
    body = _body(payload)

    with pytest.raises(LemonSqueezyWebhookError, match="event is not supported"):
        _parse(body, event_header="customer_created")


def test_webhook_store_must_match_configured_store() -> None:
    body = _body()

    with pytest.raises(LemonSqueezyWebhookError, match="store does not match"):
        _parse(body, expected_store_id="43")


def test_all_internal_cross_account_references_are_required() -> None:
    for missing in ("customer_ref", "order_ref", "offer_ref"):
        payload = _payload()
        del payload["meta"]["custom_data"][missing]
        body = _body(payload)

        with pytest.raises(LemonSqueezyWebhookError, match=missing):
            _parse(body)


def test_duplicate_json_keys_are_rejected_before_processing() -> None:
    body = (
        b'{"meta":{"event_name":"subscription_created",'
        b'"event_name":"subscription_cancelled",'
        b'"custom_data":{"customer_ref":"cust_123",'
        b'"order_ref":"order_456","offer_ref":"offer_pro_monthly"}},'
        b'"data":{"type":"subscriptions","id":"9001",'
        b'"attributes":{"store_id":42,"test_mode":false}}}'
    )

    with pytest.raises(LemonSqueezyWebhookError, match="duplicate keys"):
        _parse(body)


def test_test_mode_must_be_an_explicit_boolean() -> None:
    for invalid in (0, 1, "false", None):
        payload = _payload()
        payload["data"]["attributes"]["test_mode"] = invalid
        body = _body(payload)

        with pytest.raises(LemonSqueezyWebhookError, match="test_mode must be boolean"):
            _parse(body)


def test_body_size_is_bounded_before_json_parsing() -> None:
    body = b"{" + (b"x" * 1_048_576) + b"}"

    with pytest.raises(LemonSqueezyWebhookError, match="body is too large"):
        verify_lemon_squeezy_signature(
            raw_body=body,
            signature="0" * 64,
            signing_secret=SECRET,
        )


def test_payload_mapping_is_read_only_at_the_top_level() -> None:
    verified = _parse(_body())

    with pytest.raises(TypeError):
        verified.payload["meta"] = {}
