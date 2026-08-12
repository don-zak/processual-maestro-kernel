from __future__ import annotations

import base64
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from unittest.mock import Mock

import pytest

from processual_kernel.security import crypto as crypto_mod
from processual_kernel.security import keyring as keyring_mod
from processual_kernel.security.crypto import AEADAlgorithm, CryptoEnvelope
from processual_kernel.security.exceptions import DecryptionError, EncryptionError
from processual_kernel.security.keyring import CryptoKey, KeyRing, KeySource


@dataclass
class _Sample:
    name: str
    values: tuple[int, ...]


class _Choice(Enum):
    ONE = "one"


def test_canonical_json_handles_dataclasses_enums_and_nested_containers() -> None:
    payload = {
        "sample": _Sample("demo", (2, 1)),
        "choice": _Choice.ONE,
        "items": [_Choice.ONE, {1: (3, 4)}],
    }

    assert crypto_mod.canonical_json(payload) == (
        '{"choice":"one","items":["one",{"1":[3,4]}],'
        '"sample":{"name":"demo","values":[2,1]}}'
    )


def test_base64_helpers_and_key_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"x" * crypto_mod.KEY_LENGTH_BYTES
    monkeypatch.setattr(crypto_mod.os, "urandom", Mock(return_value=raw))

    encoded = crypto_mod.generate_key_b64()

    assert crypto_mod._b64decode(encoded) == raw
    assert base64.urlsafe_b64decode(encoded.encode("ascii")) == raw
    with pytest.raises(ValueError, match="invalid base64-encoded value"):
        crypto_mod._b64decode("é")


def test_normalize_key_accepts_bytes_and_b64_and_rejects_wrong_length() -> None:
    raw = b"k" * crypto_mod.KEY_LENGTH_BYTES
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")

    assert crypto_mod.normalize_key(raw) == raw
    assert crypto_mod.normalize_key(encoded) == raw
    with pytest.raises(ValueError, match="exactly 32 key bytes"):
        crypto_mod.normalize_key(b"short")


def test_aes_round_trip_and_validation_failures() -> None:
    key = b"a" * crypto_mod.KEY_LENGTH_BYTES
    other_key = b"b" * crypto_mod.KEY_LENGTH_BYTES
    envelope = crypto_mod.encrypt_aes256_gcm(b"secret", key, key_id="aes-key")

    assert envelope.algorithm == AEADAlgorithm.AES_256_GCM.value
    assert envelope.key_id == "aes-key"
    assert crypto_mod.decrypt_aes256_gcm(envelope, key) == b"secret"

    with pytest.raises(DecryptionError, match="expected AES-256-GCM"):
        crypto_mod.decrypt_aes256_gcm(
            replace(envelope, algorithm=AEADAlgorithm.CHACHA20_POLY1305.value), key
        )
    with pytest.raises(DecryptionError, match="associated data mismatch"):
        crypto_mod.decrypt_aes256_gcm(replace(envelope, aad_b64=crypto_mod._b64encode(b"bad")), key)
    with pytest.raises(DecryptionError, match="authentication error"):
        crypto_mod.decrypt_aes256_gcm(envelope, other_key)
    with pytest.raises(DecryptionError, match="plaintext checksum mismatch"):
        crypto_mod.decrypt_aes256_gcm(replace(envelope, plaintext_sha3_256="0" * 64), key)


def test_chacha_round_trip_and_validation_failures() -> None:
    key = b"c" * crypto_mod.KEY_LENGTH_BYTES
    other_key = b"d" * crypto_mod.KEY_LENGTH_BYTES
    envelope = crypto_mod.encrypt_chacha20_poly1305(b"secret", key, key_id="chacha-key")

    assert envelope.algorithm == AEADAlgorithm.CHACHA20_POLY1305.value
    assert envelope.key_id == "chacha-key"
    assert crypto_mod.decrypt_chacha20_poly1305(envelope, key) == b"secret"

    with pytest.raises(DecryptionError, match="expected ChaCha20-Poly1305"):
        crypto_mod.decrypt_chacha20_poly1305(
            replace(envelope, algorithm=AEADAlgorithm.AES_256_GCM.value), key
        )
    with pytest.raises(DecryptionError, match="associated data mismatch"):
        crypto_mod.decrypt_chacha20_poly1305(
            replace(envelope, aad_b64=crypto_mod._b64encode(b"bad")), key
        )
    with pytest.raises(DecryptionError, match="authentication error"):
        crypto_mod.decrypt_chacha20_poly1305(envelope, other_key)
    with pytest.raises(DecryptionError, match="plaintext checksum mismatch"):
        crypto_mod.decrypt_chacha20_poly1305(
            replace(envelope, plaintext_sha3_256="f" * 64), key
        )


def test_encrypt_wrappers_translate_cipher_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    key = b"e" * crypto_mod.KEY_LENGTH_BYTES

    aes = Mock()
    aes.encrypt.side_effect = RuntimeError("boom")
    monkeypatch.setattr(crypto_mod, "AESGCM", Mock(return_value=aes))
    with pytest.raises(EncryptionError, match="AES-256-GCM encryption failed"):
        crypto_mod.encrypt_aes256_gcm(b"payload", key)

    chacha = Mock()
    chacha.encrypt.side_effect = RuntimeError("boom")
    monkeypatch.setattr(crypto_mod, "ChaCha20Poly1305", Mock(return_value=chacha))
    with pytest.raises(EncryptionError, match="ChaCha20-Poly1305 encryption failed"):
        crypto_mod.encrypt_chacha20_poly1305(b"payload", key)


def test_report_encrypt_decrypt_and_rotate_between_algorithms() -> None:
    old_key = b"f" * crypto_mod.KEY_LENGTH_BYTES
    new_key = b"g" * crypto_mod.KEY_LENGTH_BYTES
    report = {"z": 2, "a": [1, 3]}

    aes_envelope = crypto_mod.encrypt_report(report, old_key, key_id="old")
    assert crypto_mod.decrypt_report(aes_envelope, old_key) == report

    chacha_envelope = crypto_mod.encrypt_report(
        report,
        old_key,
        algorithm=AEADAlgorithm.CHACHA20_POLY1305,
        key_id="old-chacha",
    )
    assert crypto_mod.decrypt_report(chacha_envelope, old_key) == report

    rotated = crypto_mod.rotate_encrypted_report(
        aes_envelope,
        old_key,
        new_key,
        "new",
        new_algorithm=AEADAlgorithm.CHACHA20_POLY1305,
    )
    assert rotated.key_id == "new"
    assert rotated.algorithm == AEADAlgorithm.CHACHA20_POLY1305.value
    assert crypto_mod.decrypt_report(rotated, new_key) == report


def test_decrypt_report_rejects_unknown_algorithm() -> None:
    envelope = CryptoEnvelope(
        algorithm="unknown",
        key_id="k",
        nonce_b64="",
        aad_b64="",
        ciphertext_b64="",
        plaintext_sha3_256="",
        ciphertext_sha3_256="",
    )

    with pytest.raises(DecryptionError, match="unsupported algorithm: unknown"):
        crypto_mod.decrypt_report(envelope, b"h" * crypto_mod.KEY_LENGTH_BYTES)


def test_get_key_source_precedence_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_B64", "present")
    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_FILE", "/tmp/key")
    monkeypatch.setattr(keyring_mod.os.path, "exists", Mock(return_value=True))
    assert keyring_mod.get_key_source() == KeySource.ENV

    monkeypatch.delenv("PROCESSUAL_CRYPTO_KEY_B64")
    assert keyring_mod.get_key_source() == KeySource.FILE

    monkeypatch.delenv("PROCESSUAL_CRYPTO_KEY_FILE")
    assert keyring_mod.get_key_source() == KeySource.KUBERNETES

    keyring_mod.os.path.exists.return_value = False
    assert keyring_mod.get_key_source() == KeySource.ENV


def test_load_key_from_env_with_explicit_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"i" * crypto_mod.KEY_LENGTH_BYTES
    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_B64", base64.urlsafe_b64encode(raw).decode("ascii"))
    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_ID", "primary")
    monkeypatch.setenv("PROCESSUAL_CRYPTO_ALGORITHM", "ChaCha20-Poly1305")

    key = keyring_mod.load_key_from_env()

    assert key == CryptoKey(
        key_id="primary",
        key_bytes=raw,
        source=KeySource.ENV,
        algorithm="ChaCha20-Poly1305",
        created_at=key.created_at,
    )


def test_load_key_from_file_and_missing_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "crypto.key"
    path.write_bytes(b"j" * crypto_mod.KEY_LENGTH_BYTES + b"\n")
    monkeypatch.delenv("PROCESSUAL_CRYPTO_KEY_B64", raising=False)
    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_FILE", str(path))
    monkeypatch.delenv("PROCESSUAL_CRYPTO_KEY_ID", raising=False)
    monkeypatch.delenv("PROCESSUAL_CRYPTO_ALGORITHM", raising=False)

    key = keyring_mod.load_key_from_env()
    assert key.key_id == "file-key"
    assert key.key_bytes == b"j" * crypto_mod.KEY_LENGTH_BYTES
    assert key.source == KeySource.FILE
    assert key.algorithm == "AES-256-GCM"

    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="no crypto key found"):
        keyring_mod.load_key_from_env()


def test_keyring_add_get_list_overwrite_missing_and_load(monkeypatch: pytest.MonkeyPatch) -> None:
    ring = KeyRing()
    first = CryptoKey("a", b"1" * 32, KeySource.ENV)
    second = CryptoKey("b", b"2" * 32, KeySource.FILE)
    replacement = CryptoKey("a", b"3" * 32, KeySource.VAULT)

    ring.add_key(first)
    ring.add_key(second)
    ring.add_key(replacement)

    assert ring.list_keys() == ["a", "b"]
    assert ring.get_key("a") is replacement
    with pytest.raises(KeyError, match="key not found: missing"):
        ring.get_key("missing")

    loaded = CryptoKey("env", b"4" * 32, KeySource.ENV)
    monkeypatch.setattr(keyring_mod, "load_key_from_env", Mock(return_value=loaded))
    assert ring.load_from_env() is loaded
    assert ring.get_key("env") is loaded
