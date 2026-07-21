from __future__ import annotations

import re

import pytest

from processual_api.auth.token_material import TokenDigester


def test_tokens_are_random_and_persisted_form_is_hmac_only() -> None:
    digester = TokenDigester(b"p" * 32)

    first = digester.generate_token(purpose="refresh_token")
    second = digester.generate_token(purpose="refresh_token")

    assert first.raw != second.raw
    assert first.digest != second.digest
    assert len(first.digest) == 64
    assert first.raw not in first.digest
    assert digester.matches(first.raw, first.digest, purpose="refresh_token") is True
    assert digester.matches(first.raw, first.digest, purpose="action_token") is False


def test_recovery_codes_are_human_readable_but_hash_only_at_rest() -> None:
    digester = TokenDigester(b"r" * 32)
    material = digester.generate_recovery_code()

    assert re.fullmatch(r"[A-Z2-7]{4}(?:-[A-Z2-7]{4}){3}", material.raw)
    assert len(material.digest) == 64
    assert material.raw not in material.digest
    assert digester.matches(
        material.raw,
        material.digest,
        purpose="mfa_recovery_code",
    )


def test_token_digester_rejects_weak_pepper_and_empty_domains() -> None:
    with pytest.raises(ValueError):
        TokenDigester(b"short")

    digester = TokenDigester(b"x" * 32)
    with pytest.raises(ValueError):
        digester.digest("value", purpose="")
    with pytest.raises(ValueError):
        digester.digest("", purpose="action_token")
