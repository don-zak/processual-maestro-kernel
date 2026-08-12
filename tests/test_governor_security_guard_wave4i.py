from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import processual_api.cgt_governor.security.guard as guard
import processual_kernel.security.crypto as crypto
import processual_kernel.security.keyring as keyring


KEY = b"k" * 32


def test_get_crypto_key_returns_loaded_key_bytes(monkeypatch) -> None:
    load_key = Mock(return_value=SimpleNamespace(key_bytes=KEY))
    monkeypatch.setattr(keyring, "load_key_from_env", load_key)

    result = guard.get_crypto_key()

    assert result == KEY
    load_key.assert_called_once_with()


def test_get_crypto_key_logs_and_returns_none_when_loading_fails(monkeypatch) -> None:
    failure = ValueError("missing key")
    monkeypatch.setattr(keyring, "load_key_from_env", Mock(side_effect=failure))
    logger = Mock()
    monkeypatch.setattr(guard, "logger", logger)

    result = guard.get_crypto_key()

    assert result is None
    logger.debug.assert_called_once_with("Crypto key not configured: %s", failure)


def test_decrypt_string_requires_configured_key(monkeypatch) -> None:
    get_key = Mock(return_value=None)
    monkeypatch.setattr(guard, "get_crypto_key", get_key)

    with pytest.raises(ValueError, match="no crypto key configured"):
        guard.decrypt_log_entry('{"ciphertext_b64": "payload"}')

    get_key.assert_called_once_with()


def test_decrypt_encrypted_dict_filters_extra_fields_before_envelope(monkeypatch) -> None:
    envelope = object()
    envelope_factory = Mock(return_value=envelope)
    decrypt_report = Mock(return_value={"eval_id": "eval-1"})
    monkeypatch.setattr(crypto, "CryptoEnvelope", envelope_factory)
    monkeypatch.setattr(crypto, "decrypt_report", decrypt_report)

    ciphertext = {
        "algorithm": "AES-256-GCM",
        "key_id": "governor-log",
        "nonce_b64": "nonce",
        "aad_b64": "aad",
        "ciphertext_b64": "ciphertext",
        "plaintext_sha3_256": "plain-hash",
        "ciphertext_sha3_256": "cipher-hash",
        "schema_version": "2.0.0",
        "created_at": "2026-08-12T20:00:00+00:00",
        "untrusted_extra": "drop-me",
    }

    result = guard.decrypt_log_entry(ciphertext, KEY)

    assert result == {"eval_id": "eval-1"}
    envelope_factory.assert_called_once_with(
        algorithm="AES-256-GCM",
        key_id="governor-log",
        nonce_b64="nonce",
        aad_b64="aad",
        ciphertext_b64="ciphertext",
        plaintext_sha3_256="plain-hash",
        ciphertext_sha3_256="cipher-hash",
        schema_version="2.0.0",
        created_at="2026-08-12T20:00:00+00:00",
    )
    decrypt_report.assert_called_once_with(envelope, KEY)
