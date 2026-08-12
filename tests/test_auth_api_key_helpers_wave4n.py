from __future__ import annotations

from unittest.mock import Mock

import pytest

from processual_api.auth import security as security_mod


def test_pbkdf2_hash_and_verify_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security_mod.secrets, "token_bytes", lambda _size: b"0123456789abcdef")

    hashed = security_mod._pbkdf2_hash_api_key("secret", iterations=1000)

    assert hashed.startswith("pbkdf2_sha256$1000$")
    assert security_mod._verify_pbkdf2_api_key("secret", hashed) is True
    assert security_mod._verify_pbkdf2_api_key("wrong", hashed) is False


@pytest.mark.parametrize(
    "hashed",
    [
        "bcrypt$1000$c2FsdA==$ZGlnZXN0",
        "pbkdf2_sha256$not-an-int$c2FsdA==$ZGlnZXN0",
        "pbkdf2_sha256$1000$%%%$ZGlnZXN0",
        "pbkdf2_sha256$1000$c2FsdA==$%%%",
        "missing-fields",
    ],
)
def test_verify_pbkdf2_rejects_malformed_hashes(hashed: str) -> None:
    assert security_mod._verify_pbkdf2_api_key("secret", hashed) is False


def test_verify_api_key_dispatches_pbkdf2_without_bcrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = Mock(return_value=True)
    monkeypatch.setattr(security_mod, "_verify_pbkdf2_api_key", verifier)
    monkeypatch.setattr(security_mod, "_bcrypt_lib", None)

    assert security_mod.verify_api_key("plain", "pbkdf2_sha256$payload") is True
    verifier.assert_called_once_with("plain", "pbkdf2_sha256$payload")


def test_verify_api_key_bcrypt_path_and_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    bcrypt = Mock()
    bcrypt.checkpw.return_value = True
    monkeypatch.setattr(security_mod, "_bcrypt_lib", bcrypt)

    assert security_mod.verify_api_key("plain", "bcrypt-hash") is True
    bcrypt.checkpw.assert_called_once_with(b"plain", b"bcrypt-hash")

    monkeypatch.setattr(security_mod, "_bcrypt_lib", None)
    with pytest.raises(RuntimeError, match="bcrypt is not installed"):
        security_mod.verify_api_key("plain", "bcrypt-hash")


def test_hash_api_key_uses_bcrypt_and_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    bcrypt = Mock()
    bcrypt.gensalt.return_value = b"salt"
    bcrypt.hashpw.return_value = b"hashed"
    monkeypatch.setattr(security_mod, "_bcrypt_lib", bcrypt)

    assert security_mod.hash_api_key("plain") == "hashed"
    bcrypt.gensalt.assert_called_once_with()
    bcrypt.hashpw.assert_called_once_with(b"plain", b"salt")

    monkeypatch.setattr(security_mod, "_bcrypt_lib", None)
    with pytest.raises(RuntimeError, match="bcrypt is not installed"):
        security_mod.hash_api_key("plain")


def test_pbkdf2_compat_bcrypt_delegates_to_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    hasher = Mock(return_value="pbkdf2-hash")
    verifier = Mock(return_value=True)
    monkeypatch.setattr(security_mod, "_pbkdf2_hash_api_key", hasher)
    monkeypatch.setattr(security_mod, "_verify_pbkdf2_api_key", verifier)

    assert security_mod._PBKDF2CompatBcrypt.gensalt() == b""
    assert security_mod._PBKDF2CompatBcrypt.hashpw(b"secret", b"ignored") == b"pbkdf2-hash"
    assert security_mod._PBKDF2CompatBcrypt.checkpw(b"secret", b"stored") is True
    hasher.assert_called_once_with("secret")
    verifier.assert_called_once_with("secret", "stored")


def test_generate_api_key_uses_pmk_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    token_urlsafe = Mock(return_value="deterministic-token")
    monkeypatch.setattr(security_mod.secrets, "token_urlsafe", token_urlsafe)

    assert security_mod.generate_api_key() == "pmk_deterministic-token"
    token_urlsafe.assert_called_once_with(32)
