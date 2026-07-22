from __future__ import annotations

import pytest

from processual_api.auth.mfa_crypto import EncryptedMfaSecret, MfaSecretCipher
from processual_api.auth.totp import (
    build_totp_provisioning_uri,
    totp_code_for_step,
    verify_totp,
)


def test_mfa_secret_cipher_round_trip_is_bound_to_factor_and_user():
    cipher = MfaSecretCipher(current_key_version="v1", keys={"v1": b"k" * 32})
    secret = b"JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
    encrypted = cipher.encrypt(secret, factor_id="factor-1", user_id="user-1")

    assert secret not in encrypted.ciphertext
    assert cipher.decrypt(encrypted, factor_id="factor-1", user_id="user-1") == secret

    with pytest.raises(ValueError):
        cipher.decrypt(encrypted, factor_id="factor-2", user_id="user-1")


def test_mfa_secret_cipher_rejects_tampering_and_unknown_key_versions():
    cipher = MfaSecretCipher(current_key_version="v1", keys={"v1": b"k" * 32})
    encrypted = cipher.encrypt(
        b"JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        factor_id="factor-1",
        user_id="user-1",
    )
    tampered = EncryptedMfaSecret(encrypted.ciphertext[:-1] + b"x", encrypted.key_version)

    with pytest.raises(ValueError):
        cipher.decrypt(tampered, factor_id="factor-1", user_id="user-1")
    with pytest.raises(ValueError):
        cipher.decrypt(
            EncryptedMfaSecret(encrypted.ciphertext, "retired"),
            factor_id="factor-1",
            user_id="user-1",
        )


def test_totp_matches_rfc_6238_sha1_vector_and_rejects_bad_codes():
    secret = b"12345678901234567890"
    step = 59 // 30

    assert totp_code_for_step(secret, step) == "287082"
    six_digit = totp_code_for_step(secret, step)
    assert verify_totp(secret, six_digit, at_time=59).matched_step == step
    assert verify_totp(secret, "000000", at_time=59).accepted is False
    assert verify_totp(secret, "not-a-code", at_time=59).accepted is False


def test_provisioning_uri_contains_no_unescaped_account_authority():
    uri = build_totp_provisioning_uri(
        secret=b"12345678901234567890",
        account_name="person+pilot@example.com",
        issuer="Processual Maestro",
    )

    assert uri.startswith("otpauth://totp/Processual%20Maestro%3Aperson%2Bpilot%40example.com?")
    assert "issuer=Processual%20Maestro" in uri
