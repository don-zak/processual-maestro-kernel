from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .crypto import (
    AEADAlgorithm,
    CryptoEnvelope,
    decrypt_report,
    encrypt_report,
)


class CryptoEnvelopeSchema(str, Enum):
    V1 = "processual-crypto-envelope-2.0.0"


@dataclass(frozen=True, slots=True)
class EnvelopeVerificationResult:
    valid: bool
    reason: str
    plaintext: dict[str, Any] | None = None


def build_envelope(
    report: Any,
    key: bytes | str,
    *,
    algorithm: AEADAlgorithm = AEADAlgorithm.AES_256_GCM,
    key_id: str = "default",
) -> CryptoEnvelope:
    return encrypt_report(report, key, algorithm=algorithm, key_id=key_id)


def verify_envelope(
    envelope: CryptoEnvelope,
    key: bytes | str,
) -> EnvelopeVerificationResult:
    try:
        plaintext = decrypt_report(envelope, key)
        return EnvelopeVerificationResult(
            valid=True,
            reason="decryption and checksum verification passed",
            plaintext=plaintext,
        )
    except Exception as exc:
        return EnvelopeVerificationResult(
            valid=False,
            reason=str(exc),
        )
