from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

MINIMUM_PEPPER_BYTES = 32
TOKEN_BYTES = 32
RECOVERY_CODE_BYTES = 10


@dataclass(frozen=True, slots=True)
class TokenMaterial:
    raw: str
    digest: str


class TokenDigester:
    def __init__(self, pepper: bytes) -> None:
        if not isinstance(pepper, bytes) or len(pepper) < MINIMUM_PEPPER_BYTES:
            raise ValueError("Token pepper must contain at least 32 bytes.")
        self._pepper = pepper

    def digest(self, raw_value: str, *, purpose: str) -> str:
        if not isinstance(raw_value, str) or not raw_value:
            raise ValueError("raw_value must be a non-empty string.")
        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("purpose must be a non-empty string.")
        message = f"pmk-auth-v1:{purpose}:{raw_value}".encode()
        return hmac.new(self._pepper, message, hashlib.sha256).hexdigest()

    def matches(self, raw_value: str, expected_digest: str, *, purpose: str) -> bool:
        if not isinstance(expected_digest, str):
            return False
        try:
            candidate = self.digest(raw_value, purpose=purpose)
        except ValueError:
            return False
        return hmac.compare_digest(candidate, expected_digest)

    def generate_token(self, *, purpose: str) -> TokenMaterial:
        raw = secrets.token_urlsafe(TOKEN_BYTES)
        return TokenMaterial(raw=raw, digest=self.digest(raw, purpose=purpose))

    def generate_recovery_code(self) -> TokenMaterial:
        raw_bytes = secrets.token_bytes(RECOVERY_CODE_BYTES)
        compact = base64.b32encode(raw_bytes).decode("ascii").rstrip("=")
        raw = f"{compact[:4]}-{compact[4:8]}-{compact[8:12]}-{compact[12:]}"
        return TokenMaterial(
            raw=raw,
            digest=self.digest(raw, purpose="mfa_recovery_code"),
        )


__all__ = ["TokenDigester", "TokenMaterial"]
