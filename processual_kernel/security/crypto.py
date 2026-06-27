from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305

from .exceptions import DecryptionError, EncryptionError
from .hashes import sha3_256_hex_bytes


class AEADAlgorithm(str, Enum):
    AES_256_GCM = "AES-256-GCM"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"


KEY_LENGTH_BYTES = 32
NONCE_LENGTH_BYTES = 12
ENVELOPE_SCHEMA_VERSION = "processual-crypto-envelope-2.0.0"


@dataclass(frozen=True, slots=True)
class CryptoEnvelope:
    algorithm: str
    key_id: str
    nonce_b64: str
    aad_b64: str
    ciphertext_b64: str
    plaintext_sha3_256: str
    ciphertext_sha3_256: str
    schema_version: str = ENVELOPE_SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _safe_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_safe_dict(item) for item in value]
    if isinstance(value, list):
        return [_safe_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _safe_dict(v) for k, v in value.items()}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_safe_dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:
        raise ValueError("invalid base64-encoded value") from exc


def generate_key_b64() -> str:
    return _b64encode(os.urandom(KEY_LENGTH_BYTES))


def normalize_key(key: bytes | str) -> bytes:
    raw = key if isinstance(key, bytes) else _b64decode(key)
    if len(raw) != KEY_LENGTH_BYTES:
        raise ValueError(f"AEAD requires exactly {KEY_LENGTH_BYTES} key bytes, got {len(raw)}")
    return raw


def _build_aad(algorithm: str, key_id: str, schema_version: str) -> bytes:
    aad = {
        "algorithm": algorithm,
        "key_id": key_id,
        "schema_version": schema_version,
        "nonce_length": NONCE_LENGTH_BYTES,
    }
    return canonical_json(aad).encode("utf-8")


def encrypt_aes256_gcm(plaintext: bytes, key: bytes | str, key_id: str = "default") -> CryptoEnvelope:
    raw_key = normalize_key(key)
    aad = _build_aad(AEADAlgorithm.AES_256_GCM.value, key_id, ENVELOPE_SCHEMA_VERSION)
    nonce = os.urandom(NONCE_LENGTH_BYTES)
    try:
        ciphertext = AESGCM(raw_key).encrypt(nonce, plaintext, aad)
    except Exception as exc:
        raise EncryptionError("AES-256-GCM encryption failed") from exc
    return CryptoEnvelope(
        algorithm=AEADAlgorithm.AES_256_GCM.value,
        key_id=key_id,
        nonce_b64=_b64encode(nonce),
        aad_b64=_b64encode(aad),
        ciphertext_b64=_b64encode(ciphertext),
        plaintext_sha3_256=sha3_256_hex_bytes(plaintext),
        ciphertext_sha3_256=sha3_256_hex_bytes(ciphertext),
    )


def decrypt_aes256_gcm(envelope: CryptoEnvelope, key: bytes | str) -> bytes:
    if envelope.algorithm != AEADAlgorithm.AES_256_GCM.value:
        raise DecryptionError(f"expected AES-256-GCM, got {envelope.algorithm}")
    raw_key = normalize_key(key)
    nonce = _b64decode(envelope.nonce_b64)
    ciphertext = _b64decode(envelope.ciphertext_b64)
    aad = _b64decode(envelope.aad_b64)
    expected_aad = _build_aad(envelope.algorithm, envelope.key_id, envelope.schema_version)
    if aad != expected_aad:
        raise DecryptionError("associated data mismatch")
    try:
        plaintext = AESGCM(raw_key).decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise DecryptionError("AES-256-GCM decryption failed (authentication error)") from exc
    actual_sha3 = sha3_256_hex_bytes(plaintext)
    if actual_sha3 != envelope.plaintext_sha3_256:
        raise DecryptionError("plaintext checksum mismatch")
    return plaintext


def encrypt_chacha20_poly1305(plaintext: bytes, key: bytes | str, key_id: str = "default") -> CryptoEnvelope:
    raw_key = normalize_key(key)
    aad = _build_aad(AEADAlgorithm.CHACHA20_POLY1305.value, key_id, ENVELOPE_SCHEMA_VERSION)
    nonce = os.urandom(NONCE_LENGTH_BYTES)
    try:
        ciphertext = ChaCha20Poly1305(raw_key).encrypt(nonce, plaintext, aad)
    except Exception as exc:
        raise EncryptionError("ChaCha20-Poly1305 encryption failed") from exc
    return CryptoEnvelope(
        algorithm=AEADAlgorithm.CHACHA20_POLY1305.value,
        key_id=key_id,
        nonce_b64=_b64encode(nonce),
        aad_b64=_b64encode(aad),
        ciphertext_b64=_b64encode(ciphertext),
        plaintext_sha3_256=sha3_256_hex_bytes(plaintext),
        ciphertext_sha3_256=sha3_256_hex_bytes(ciphertext),
    )


def decrypt_chacha20_poly1305(envelope: CryptoEnvelope, key: bytes | str) -> bytes:
    if envelope.algorithm != AEADAlgorithm.CHACHA20_POLY1305.value:
        raise DecryptionError(f"expected ChaCha20-Poly1305, got {envelope.algorithm}")
    raw_key = normalize_key(key)
    nonce = _b64decode(envelope.nonce_b64)
    ciphertext = _b64decode(envelope.ciphertext_b64)
    aad = _b64decode(envelope.aad_b64)
    expected_aad = _build_aad(envelope.algorithm, envelope.key_id, envelope.schema_version)
    if aad != expected_aad:
        raise DecryptionError("associated data mismatch")
    try:
        plaintext = ChaCha20Poly1305(raw_key).decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise DecryptionError("ChaCha20-Poly1305 decryption failed (authentication error)") from exc
    actual_sha3 = sha3_256_hex_bytes(plaintext)
    if actual_sha3 != envelope.plaintext_sha3_256:
        raise DecryptionError("plaintext checksum mismatch")
    return plaintext


def encrypt_report(
    report: Any,
    key: bytes | str,
    *,
    algorithm: AEADAlgorithm = AEADAlgorithm.AES_256_GCM,
    key_id: str = "default",
) -> CryptoEnvelope:
    payload = canonical_json(report).encode("utf-8")
    if algorithm == AEADAlgorithm.AES_256_GCM:
        return encrypt_aes256_gcm(payload, key, key_id=key_id)
    return encrypt_chacha20_poly1305(payload, key, key_id=key_id)


def decrypt_report(
    envelope: CryptoEnvelope,
    key: bytes | str,
) -> dict[str, Any]:
    if envelope.algorithm == AEADAlgorithm.AES_256_GCM.value:
        plaintext = decrypt_aes256_gcm(envelope, key)
    elif envelope.algorithm == AEADAlgorithm.CHACHA20_POLY1305.value:
        plaintext = decrypt_chacha20_poly1305(envelope, key)
    else:
        raise DecryptionError(f"unsupported algorithm: {envelope.algorithm}")
    return json.loads(plaintext.decode("utf-8"))


def rotate_encrypted_report(
    old_envelope: CryptoEnvelope,
    old_key: bytes | str,
    new_key: bytes | str,
    new_key_id: str,
    new_algorithm: AEADAlgorithm = AEADAlgorithm.AES_256_GCM,
) -> CryptoEnvelope:
    plaintext = decrypt_report(old_envelope, old_key)
    return encrypt_report(
        plaintext,
        new_key,
        algorithm=new_algorithm,
        key_id=new_key_id,
    )
