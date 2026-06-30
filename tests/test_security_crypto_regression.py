import hashlib

import pytest

import processual_api.cgt_governor.security.guard as guard
from processual_kernel.security import crypto
from processual_kernel.security.envelopes import build_envelope, verify_envelope
from processual_kernel.security.exceptions import DecryptionError
from processual_kernel.security.hashes import sha256_hex_bytes, sha3_256_hex_bytes
from processual_kernel.security.keyring import CryptoKey, KeyRing, KeySource, load_key_from_env
from processual_kernel.security.policies import EncryptionPolicy, SecurityPolicy


KEY_A = b"a" * crypto.KEY_LENGTH_BYTES
KEY_B = b"b" * crypto.KEY_LENGTH_BYTES


def test_sign_response_uses_canonical_json_ordering():
    first = {"b": 2, "a": 1}
    second = {"a": 1, "b": 2}

    assert guard.sign_response(first) == guard.sign_response(second)
    assert guard.sign_response(first) == guard.sign_bytes(
        crypto.canonical_json(second).encode("utf-8")
    )


def test_hash_helpers_match_hashlib():
    payload = b"processual-maestro-security"

    assert sha256_hex_bytes(payload) == hashlib.sha256(payload).hexdigest()
    assert sha3_256_hex_bytes(payload) == hashlib.sha3_256(payload).hexdigest()
    assert len(sha3_256_hex_bytes(payload)) == 64


def test_crypto_key_generation_and_normalization_round_trip():
    key_b64 = crypto.generate_key_b64()
    normalized = crypto.normalize_key(key_b64)

    assert isinstance(normalized, bytes)
    assert len(normalized) == crypto.KEY_LENGTH_BYTES
    assert crypto.normalize_key(normalized) == normalized

    with pytest.raises(ValueError):
        crypto.normalize_key(b"too-short")


def test_encrypt_decrypt_report_with_aes_and_chacha():
    report = {
        "eval_id": "eval_crypto_1",
        "rank": "stable",
        "reward": 0.91,
        "nested": {"ar": "قبول", "items": [1, 2, 3]},
    }

    aes_envelope = crypto.encrypt_report(
        report,
        KEY_A,
        algorithm=crypto.AEADAlgorithm.AES_256_GCM,
        key_id="aes-key",
    )
    chacha_envelope = crypto.encrypt_report(
        report,
        KEY_A,
        algorithm=crypto.AEADAlgorithm.CHACHA20_POLY1305,
        key_id="chacha-key",
    )

    assert aes_envelope.algorithm == crypto.AEADAlgorithm.AES_256_GCM.value
    assert chacha_envelope.algorithm == crypto.AEADAlgorithm.CHACHA20_POLY1305.value

    assert crypto.decrypt_report(aes_envelope, KEY_A) == report
    assert crypto.decrypt_report(chacha_envelope, KEY_A) == report

    with pytest.raises(DecryptionError):
        crypto.decrypt_report(aes_envelope, KEY_B)


def test_rotate_encrypted_report_changes_key_and_preserves_plaintext():
    report = {
        "eval_id": "eval_rotate_1",
        "rank": "hybrid",
        "reward": 0.44,
    }

    old_envelope = crypto.encrypt_report(report, KEY_A, key_id="old-key")
    rotated = crypto.rotate_encrypted_report(
        old_envelope,
        KEY_A,
        KEY_B,
        new_key_id="new-key",
        new_algorithm=crypto.AEADAlgorithm.CHACHA20_POLY1305,
    )

    assert rotated.key_id == "new-key"
    assert rotated.algorithm == crypto.AEADAlgorithm.CHACHA20_POLY1305.value
    assert crypto.decrypt_report(rotated, KEY_B) == report

    with pytest.raises(DecryptionError):
        crypto.decrypt_report(rotated, KEY_A)


def test_envelope_verification_reports_success_and_failure():
    report = {"eval_id": "eval_verify_1", "rank": "stable"}

    envelope = build_envelope(report, KEY_A, key_id="verify-key")

    ok = verify_envelope(envelope, KEY_A)
    assert ok.valid is True
    assert ok.plaintext == report
    assert "passed" in ok.reason

    failed = verify_envelope(envelope, KEY_B)
    assert failed.valid is False
    assert failed.plaintext is None
    assert failed.reason


def test_guard_encrypt_log_entry_dev_fallback_and_encrypted_round_trip(monkeypatch):
    entry = {
        "eval_id": "eval_guard_1",
        "rank": "stable",
        "reward": 0.91,
        "policy_label": "Accept",
    }

    monkeypatch.setattr(guard, "get_crypto_key", lambda: None)

    assert guard.encrypt_log_entry(entry) is entry
    assert guard.decrypt_log_entry(entry) is entry

    encrypted = guard.encrypt_log_entry(entry, KEY_A)
    assert isinstance(encrypted, str)
    assert "ciphertext_b64" in encrypted

    decrypted_from_string = guard.decrypt_log_entry(encrypted, KEY_A)
    assert decrypted_from_string == entry

    encrypted_as_dict = crypto.canonical_json(
        crypto.encrypt_report(entry, KEY_A, key_id="governor-log")
    )
    decrypted_from_dict = guard.decrypt_log_entry(
        __import__("json").loads(encrypted_as_dict),
        KEY_A,
    )
    assert decrypted_from_dict == entry

    encrypted_dict = __import__("json").loads(encrypted)
    monkeypatch.setattr(guard, "get_crypto_key", lambda: None)
    with pytest.raises(ValueError):
        guard.decrypt_log_entry(encrypted_dict)


def test_keyring_load_from_env_and_lookup(monkeypatch):
    key_b64 = crypto.generate_key_b64()

    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_B64", key_b64)
    monkeypatch.setenv("PROCESSUAL_CRYPTO_KEY_ID", "test-env-key")
    monkeypatch.setenv("PROCESSUAL_CRYPTO_ALGORITHM", "AES-256-GCM")
    monkeypatch.delenv("PROCESSUAL_CRYPTO_KEY_FILE", raising=False)

    loaded = load_key_from_env()

    assert loaded.key_id == "test-env-key"
    assert loaded.source == KeySource.ENV
    assert loaded.algorithm == "AES-256-GCM"
    assert len(loaded.key_bytes) == crypto.KEY_LENGTH_BYTES

    keyring = KeyRing()
    keyring.add_key(loaded)
    keyring.add_key(
        CryptoKey(
            key_id="manual-key",
            key_bytes=KEY_A,
            source=KeySource.ENV,
        )
    )

    assert keyring.get_key("test-env-key") == loaded
    assert set(keyring.list_keys()) == {"test-env-key", "manual-key"}

    with pytest.raises(KeyError):
        keyring.get_key("missing-key")


def test_security_policy_defaults_are_strict_enough():
    policy = SecurityPolicy()

    assert policy.encryption == EncryptionPolicy.ALWAYS_ENCRYPT
    assert policy.min_key_length == 32
    assert "AES-256-GCM" in policy.allowed_algorithms
    assert "ChaCha20-Poly1305" in policy.allowed_algorithms
    assert policy.require_sha3_256 is True
    assert policy.require_key_id is True
    assert policy.audit_failures is True