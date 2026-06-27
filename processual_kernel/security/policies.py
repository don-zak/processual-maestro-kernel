from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EncryptionPolicy(str, Enum):
    ALWAYS_ENCRYPT = "always_encrypt"
    ENCRYPT_SENSITIVE = "encrypt_sensitive"
    PLAINTEXT_ALLOWED = "plaintext_allowed"


@dataclass(frozen=True, slots=True)
class SecurityPolicy:
    encryption: EncryptionPolicy = EncryptionPolicy.ALWAYS_ENCRYPT
    min_key_length: int = 32
    allowed_algorithms: tuple[str, ...] = ("AES-256-GCM", "ChaCha20-Poly1305")
    require_sha3_256: bool = True
    require_key_id: bool = True
    max_report_age_days: int = 90
    audit_failures: bool = True
