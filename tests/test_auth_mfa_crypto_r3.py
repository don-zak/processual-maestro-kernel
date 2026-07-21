from __future__ import annotations

import pytest

from processual_api.auth.mfa_crypto import EncryptedMfaSecret, MfaSecretCipher


def test_totp_secret_round_trip_is_bound_to_user_and_factor() -> None:
    cipher = MfaSecretCipher(current_key_version="v1", keys={"v1": b"a" * 32})
    secret = b"01234567890123456789"

    encrypted = cipher.encrypt(secret, user_id="user-1", factor_id="factor-1")

    assert encrypted.ciphertext != secret
    assert secret not in encrypted.ciphertext
    assert encrypted.key_version == "v1"
    assert (
        cipher.decrypt(
            encrypted,
            user_id="user-1",
            factor_id="factor-1",
        )
        == secret
    )

    with pytest.raises(ValueError, match="authentication failed"):
        cipher.decrypt(encrypted, user_id="user-2", factor_id="factor-1")


def test_key_rotation_reencrypts_with_current_version() -> None:
    old_cipher = MfaSecretCipher(current_key_version="v1", keys={"v1": b"a" * 32})
    encrypted = old_cipher.encrypt(
        b"01234567890123456789",
        user_id="user-1",
        factor_id="factor-1",
    )
    rotating_cipher = MfaSecretCipher(
        current_key_version="v2",
        keys={"v1": b"a" * 32, "v2": b"b" * 32},
    )

    rotated = rotating_cipher.rotate(
        encrypted,
        user_id="user-1",
        factor_id="factor-1",
    )

    assert rotated.key_version == "v2"
    assert rotated.ciphertext != encrypted.ciphertext
    assert (
        rotating_cipher.decrypt(
            rotated,
            user_id="user-1",
            factor_id="factor-1",
        )
        == b"01234567890123456789"
    )


def test_cipher_rejects_missing_keys_truncation_and_tampering() -> None:
    with pytest.raises(ValueError):
        MfaSecretCipher(current_key_version="v1", keys={})
    with pytest.raises(ValueError):
        MfaSecretCipher(current_key_version="v1", keys={"v1": b"short"})

    cipher = MfaSecretCipher(current_key_version="v1", keys={"v1": b"a" * 32})
    with pytest.raises(ValueError, match="truncated"):
        cipher.decrypt(
            EncryptedMfaSecret(ciphertext=b"short", key_version="v1"),
            user_id="user-1",
            factor_id="factor-1",
        )

    encrypted = cipher.encrypt(
        b"01234567890123456789",
        user_id="user-1",
        factor_id="factor-1",
    )
    tampered = EncryptedMfaSecret(
        ciphertext=encrypted.ciphertext[:-1] + bytes([encrypted.ciphertext[-1] ^ 1]),
        key_version="v1",
    )
    with pytest.raises(ValueError, match="authentication failed"):
        cipher.decrypt(tampered, user_id="user-1", factor_id="factor-1")
