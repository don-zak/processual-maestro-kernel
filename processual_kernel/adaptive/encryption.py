from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as exc:  # pragma: no cover
    AESGCM = None  # type: ignore[assignment]
    _AES_IMPORT_ERROR = exc
else:
    _AES_IMPORT_ERROR = None

from ..adaptive_types import AdaptiveReportDecryptionResult, EncryptedAdaptiveReport

AES_256_GCM = "AES-256-GCM"
KEY_LENGTH_BYTES = 32
NONCE_LENGTH_BYTES = 12


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


def sha256_hex_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _b64decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii"))
    except Exception as exc:
        raise ValueError("invalid base64-encoded AES key or encrypted report field") from exc


class AdaptiveReportEncryptor:
    """AES-256-GCM encryption for adaptive reports and evidence packs.

    This layer is outside the core kernel. It never changes Ψ equations, policy decisions, or cgtlib behavior.
    Raw keys are caller-managed and are never embedded in encrypted reports, evidence packs, or audit events.
    """

    @staticmethod
    def generate_key_b64() -> str:
        return _b64encode(os.urandom(KEY_LENGTH_BYTES))

    @staticmethod
    def normalize_key(key: bytes | str) -> bytes:
        raw = key if isinstance(key, bytes) else _b64decode(key)
        if len(raw) != KEY_LENGTH_BYTES:
            raise ValueError("AES-256-GCM requires exactly 32 key bytes")
        return raw

    @staticmethod
    def associated_data(workflow_id: str, report_kind: str, key_id: str, plaintext_schema_version: str) -> bytes:
        aad = {
            "workflow_id": workflow_id,
            "report_kind": report_kind,
            "key_id": key_id,
            "plaintext_schema_version": plaintext_schema_version,
            "algorithm": AES_256_GCM,
        }
        return canonical_json(aad).encode("utf-8")

    def encrypt_report(
        self,
        workflow_id: str,
        report: Any,
        key: bytes | str,
        *,
        report_kind: str,
        key_id: str = "default",
    ) -> EncryptedAdaptiveReport:
        if AESGCM is None:  # pragma: no cover
            raise RuntimeError("cryptography is required for AES-256-GCM report encryption") from _AES_IMPORT_ERROR
        raw_key = self.normalize_key(key)
        artifact = _safe_dict(report)
        plaintext_schema_version = (
            str(artifact.get("schema_version", report.__class__.__name__))
            if isinstance(artifact, dict)
            else report.__class__.__name__
        )
        plaintext = canonical_json(artifact).encode("utf-8")
        nonce = os.urandom(NONCE_LENGTH_BYTES)
        aad = self.associated_data(workflow_id, report_kind, key_id, plaintext_schema_version)
        ciphertext = AESGCM(raw_key).encrypt(nonce, plaintext, aad)
        return EncryptedAdaptiveReport(
            workflow_id=workflow_id,
            report_kind=report_kind,
            algorithm=AES_256_GCM,
            key_id=key_id,
            nonce_b64=_b64encode(nonce),
            aad_b64=_b64encode(aad),
            ciphertext_b64=_b64encode(ciphertext),
            plaintext_sha256=sha256_hex_bytes(plaintext),
            ciphertext_sha256=sha256_hex_bytes(ciphertext),
            plaintext_schema_version=plaintext_schema_version,
        )

    def decrypt_report(self, encrypted: EncryptedAdaptiveReport, key: bytes | str) -> AdaptiveReportDecryptionResult:
        if AESGCM is None:  # pragma: no cover
            raise RuntimeError("cryptography is required for AES-256-GCM report decryption") from _AES_IMPORT_ERROR
        if encrypted.algorithm != AES_256_GCM:
            return AdaptiveReportDecryptionResult(
                workflow_id=encrypted.workflow_id,
                report_kind=encrypted.report_kind,
                valid=False,
                reason=f"unsupported encryption algorithm: {encrypted.algorithm}",
            )
        raw_key = self.normalize_key(key)
        nonce = _b64decode(encrypted.nonce_b64)
        ciphertext = _b64decode(encrypted.ciphertext_b64)
        aad = _b64decode(encrypted.aad_b64)
        expected_aad = self.associated_data(
            encrypted.workflow_id,
            encrypted.report_kind,
            encrypted.key_id,
            encrypted.plaintext_schema_version,
        )
        if aad != expected_aad:
            return AdaptiveReportDecryptionResult(
                workflow_id=encrypted.workflow_id,
                report_kind=encrypted.report_kind,
                valid=False,
                reason="associated data does not match encrypted report metadata",
            )
        try:
            plaintext = AESGCM(raw_key).decrypt(nonce, ciphertext, aad)
        except Exception:
            return AdaptiveReportDecryptionResult(
                workflow_id=encrypted.workflow_id,
                report_kind=encrypted.report_kind,
                valid=False,
                ciphertext_sha256=sha256_hex_bytes(ciphertext),
                reason="AES-GCM authentication failed",
            )
        plaintext_hash = sha256_hex_bytes(plaintext)
        valid = plaintext_hash == encrypted.plaintext_sha256
        return AdaptiveReportDecryptionResult(
            workflow_id=encrypted.workflow_id,
            report_kind=encrypted.report_kind,
            valid=valid,
            artifact=json.loads(plaintext.decode("utf-8")) if valid else None,
            plaintext_sha256=plaintext_hash,
            ciphertext_sha256=sha256_hex_bytes(ciphertext),
            reason="decryption succeeded" if valid else "plaintext checksum mismatch",
        )

    @staticmethod
    def write_encrypted_report(report: EncryptedAdaptiveReport, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_safe_dict(report), ensure_ascii=False, indent=2), encoding="utf-8")
        return target
