"""CGT Governor â€” Security Guard

Provides signing and encryption for governor data using the kernel's
existing crypto library (AES-256-GCM, ChaCha20-Poly1305, SHA3-256).

Usage:
    from .guard import sign_response, encrypt_log_entry, decrypt_log_entry
    sig = sign_response(my_dict)
    encrypted = encrypt_log_entry(my_dict, key)
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("processual_api.cgt_governor.security")


def get_crypto_key() -> bytes | None:
    """Load the 32-byte crypto key from the keyring.

    Returns None if no key is configured (safe fallback for dev mode).
    """
    try:
        from processual_kernel.security.keyring import load_key_from_env

        key = load_key_from_env()
        return key.key_bytes
    except (ImportError, ValueError, Exception) as exc:
        logger.debug("Crypto key not configured: %s", exc)
        return None


def sign_bytes(data: bytes) -> str:
    """Return SHA3-256 hex digest of arbitrary bytes."""
    from processual_kernel.security.hashes import sha3_256_hex_bytes

    return sha3_256_hex_bytes(data)


def sign_response(data: dict) -> str:
    """Return SHA3-256 hex signature of a canonical-JSON serialized dict."""
    from processual_kernel.security.crypto import canonical_json

    return sign_bytes(canonical_json(data).encode("utf-8"))


def encrypt_log_entry(entry: dict, key: bytes | None = None) -> str | dict:
    """Encrypt a log entry using AES-256-GCM.

    If no key is configured, returns the entry as-is (dev mode fallback).
    Returns base64-encoded envelope JSON string.
    """
    if key is None:
        key = get_crypto_key()
    if key is None:
        return entry

    from processual_kernel.security.crypto import canonical_json, encrypt_report

    envelope = encrypt_report(entry, key, key_id="governor-log")
    return canonical_json(envelope)


def decrypt_log_entry(ciphertext: str | dict, key: bytes | None = None) -> dict:
    """Decrypt a log entry that was encrypted with encrypt_log_entry().

    Accepts both string-encoded envelopes and dict-based envelopes.
    Plain dicts (not encrypted) are returned as-is.
    """
    if isinstance(ciphertext, dict):
        if "ciphertext_b64" not in ciphertext:
            return ciphertext
        if key is None:
            key = get_crypto_key()
        if key is None:
            raise ValueError("Cannot decrypt: no crypto key configured")
        from processual_kernel.security.crypto import CryptoEnvelope, decrypt_report
        envelope_fields = {
            "algorithm",
            "key_id",
            "nonce_b64",
            "aad_b64",
            "ciphertext_b64",
            "plaintext_sha3_256",
            "ciphertext_sha3_256",
            "schema_version",
            "created_at",
        }
        envelope_data = {k: v for k, v in ciphertext.items() if k in envelope_fields}
        envelope = CryptoEnvelope(**envelope_data)
        return decrypt_report(envelope, key)

    if key is None:
        key = get_crypto_key()
    if key is None:
        raise ValueError("Cannot decrypt: no crypto key configured")

    from processual_kernel.security.crypto import CryptoEnvelope, decrypt_report

    env_data = json.loads(ciphertext)
    envelope = CryptoEnvelope(**env_data)
    return decrypt_report(envelope, key)

