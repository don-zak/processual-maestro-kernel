from __future__ import annotations

import pytest

from processual_api.auth.totp import (
    build_totp_provisioning_uri,
    encode_totp_secret,
    generate_totp_secret,
    totp_code_for_step,
    verify_totp,
)


def test_totp_matches_rfc_6238_sha1_vector_truncated_to_six_digits() -> None:
    secret = b"12345678901234567890"
    assert totp_code_for_step(secret, 1) == "287082"
    assert verify_totp(secret, "287082", at_time=59, allowed_window=0).accepted is True


def test_totp_window_and_replay_step_are_enforced() -> None:
    secret = b"12345678901234567890"
    current_step = 100
    previous_code = totp_code_for_step(secret, current_step - 1)

    accepted = verify_totp(
        secret,
        previous_code,
        at_time=current_step * 30,
        allowed_window=1,
    )
    replayed = verify_totp(
        secret,
        previous_code,
        at_time=current_step * 30,
        allowed_window=1,
        last_used_step=current_step - 1,
    )

    assert accepted.accepted is True
    assert accepted.matched_step == current_step - 1
    assert replayed.accepted is False
    assert replayed.reason == "replayed_step"


def test_totp_rejects_malformed_codes_and_excessive_window() -> None:
    secret = b"12345678901234567890"
    assert verify_totp(secret, "12345", at_time=0).reason == "invalid_format"
    assert verify_totp(secret, "１２３４５６", at_time=0).reason == "invalid_format"
    with pytest.raises(ValueError):
        verify_totp(secret, "123456", at_time=0, allowed_window=3)


def test_totp_provisioning_uri_is_encoded_and_contains_no_issuer_ambiguity() -> None:
    secret = generate_totp_secret()
    uri = build_totp_provisioning_uri(
        secret=secret,
        account_name="user+admin@example.com",
        issuer="Processual Maestro",
    )

    assert uri.startswith("otpauth://totp/Processual%20Maestro%3Auser%2Badmin%40example.com?")
    assert f"secret={encode_totp_secret(secret)}" in uri
    assert "issuer=Processual%20Maestro" in uri
    assert "digits=6" in uri
    assert "period=30" in uri
