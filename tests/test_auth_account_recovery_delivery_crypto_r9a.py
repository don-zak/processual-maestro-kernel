import pytest

from processual_api.auth.delivery_crypto import (
    DeliveryPayloadCipher,
)


def _cipher() -> DeliveryPayloadCipher:
    return DeliveryPayloadCipher(
        current_key_version="delivery-v1",
        keys={"delivery-v1": b"k" * 32},
    )


def test_account_recovery_authority_round_trip() -> None:
    cipher = _cipher()

    authority = {
        "outbox_id": "outbox-1",
        "user_id": "user-1",
        "account_recovery_request_id": "recovery-1",
        "purpose": "account_recovery_verification",
    }

    encrypted = cipher.encrypt(
        "raw-recovery-token",
        **authority,
    )

    assert b"raw-recovery-token" not in encrypted.ciphertext
    assert (
        cipher.decrypt(
            encrypted,
            **authority,
        )
        == "raw-recovery-token"
    )


def test_recovery_authority_substitution_is_rejected() -> None:
    cipher = _cipher()

    encrypted = cipher.encrypt(
        "raw-recovery-token",
        outbox_id="outbox-1",
        user_id="user-1",
        account_recovery_request_id="recovery-1",
        purpose="account_recovery_verification",
    )

    with pytest.raises(
        ValueError,
        match="authentication failed",
    ):
        cipher.decrypt(
            encrypted,
            outbox_id="outbox-1",
            user_id="user-1",
            account_recovery_request_id="recovery-2",
            purpose="account_recovery_verification",
        )


@pytest.mark.parametrize(
    "values",
    (
        {
            "action_token_id": None,
            "account_recovery_request_id": None,
        },
        {
            "action_token_id": "action-1",
            "account_recovery_request_id": "recovery-1",
        },
    ),
)
def test_cipher_requires_exactly_one_authority(values) -> None:
    cipher = _cipher()

    with pytest.raises(
        ValueError,
        match="Exactly one",
    ):
        cipher.encrypt(
            "raw-token",
            outbox_id="outbox-1",
            user_id="user-1",
            purpose="verify_email",
            **values,
        )


def test_legacy_action_token_keyword_remains_compatible() -> None:
    cipher = _cipher()

    authority = {
        "outbox_id": "outbox-1",
        "user_id": "user-1",
        "action_token_id": "action-1",
        "purpose": "verify_email",
    }

    encrypted = cipher.encrypt(
        "legacy-token",
        **authority,
    )

    assert cipher.decrypt(encrypted, **authority) == "legacy-token"
