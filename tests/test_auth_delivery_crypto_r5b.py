from __future__ import annotations

import pytest

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
    EncryptedDeliveryPayload,
)

AUTHORITY = {
    "outbox_id": "94c494ea-88c3-45db-9b5e-ffb6c4f0d44f",
    "user_id": "ee1eb7bb-e91c-4e56-b492-7612bade75f1",
    "action_token_id": "1077e70c-175d-4e14-a29d-1c909366ab87",
    "purpose": "verify_email",
}


def test_delivery_payload_round_trip_and_ciphertext_randomization() -> None:
    cipher = DeliveryPayloadCipher(
        current_key_version="delivery-v2",
        keys={"delivery-v1": b"a" * 32, "delivery-v2": b"b" * 32},
    )

    first = cipher.encrypt("opaque-verification-token", **AUTHORITY)
    second = cipher.encrypt("opaque-verification-token", **AUTHORITY)

    assert first.key_version == "delivery-v2"
    assert first.ciphertext != second.ciphertext
    assert b"opaque-verification-token" not in first.ciphertext
    assert cipher.decrypt(first, **AUTHORITY) == "opaque-verification-token"


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("outbox_id", "different-outbox"),
        ("user_id", "different-user"),
        ("action_token_id", "different-token"),
        ("purpose", "reset_password"),
    ),
)
def test_delivery_payload_rejects_authority_substitution(field: str, replacement: str) -> None:
    cipher = DeliveryPayloadCipher(
        current_key_version="delivery-v1",
        keys={"delivery-v1": b"k" * 32},
    )
    encrypted = cipher.encrypt("opaque-verification-token", **AUTHORITY)
    changed = {**AUTHORITY, field: replacement}

    with pytest.raises(ValueError, match="authentication failed"):
        cipher.decrypt(encrypted, **changed)


def test_delivery_payload_rejects_unknown_key_and_truncation() -> None:
    cipher = DeliveryPayloadCipher(
        current_key_version="delivery-v1",
        keys={"delivery-v1": b"k" * 32},
    )

    with pytest.raises(ValueError, match="key version"):
        cipher.decrypt(
            EncryptedDeliveryPayload(ciphertext=b"x" * 40, key_version="missing"),
            **AUTHORITY,
        )

    with pytest.raises(ValueError, match="truncated"):
        cipher.decrypt(
            EncryptedDeliveryPayload(ciphertext=b"x" * 12, key_version="delivery-v1"),
            **AUTHORITY,
        )


def test_delivery_key_contract_requires_named_aes_256_keys() -> None:
    with pytest.raises(ValueError):
        DeliveryPayloadCipher(current_key_version="delivery-v1", keys={})
    with pytest.raises(ValueError):
        DeliveryPayloadCipher(
            current_key_version="delivery-v1",
            keys={"delivery-v1": b"short"},
        )
