from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from dataclasses import dataclass
from urllib.parse import quote

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_SECRET_BYTES = 20


@dataclass(frozen=True, slots=True)
class TotpVerification:
    accepted: bool
    matched_step: int | None = None
    reason: str = "invalid_code"


def generate_totp_secret() -> bytes:
    return secrets.token_bytes(TOTP_SECRET_BYTES)


def encode_totp_secret(secret: bytes) -> str:
    if not isinstance(secret, bytes) or len(secret) < TOTP_SECRET_BYTES:
        raise ValueError("TOTP secret must contain at least 20 bytes.")
    return base64.b32encode(secret).decode("ascii").rstrip("=")


def build_totp_provisioning_uri(*, secret: bytes, account_name: str, issuer: str) -> str:
    if not account_name.strip() or not issuer.strip():
        raise ValueError("account_name and issuer are required.")
    label = quote(f"{issuer}:{account_name}", safe="")
    encoded_issuer = quote(issuer, safe="")
    return (
        f"otpauth://totp/{label}?secret={encode_totp_secret(secret)}"
        f"&issuer={encoded_issuer}&algorithm=SHA1&digits={TOTP_DIGITS}"
        f"&period={TOTP_PERIOD_SECONDS}"
    )


def totp_code_for_step(secret: bytes, step: int) -> str:
    if step < 0:
        raise ValueError("TOTP step cannot be negative.")
    if not isinstance(secret, bytes) or len(secret) < TOTP_SECRET_BYTES:
        raise ValueError("TOTP secret must contain at least 20 bytes.")
    digest = hmac.new(secret, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(
    secret: bytes,
    code: str,
    *,
    at_time: float | None = None,
    allowed_window: int = 1,
    last_used_step: int | None = None,
) -> TotpVerification:
    if allowed_window < 0 or allowed_window > 2:
        raise ValueError("allowed_window must be between 0 and 2.")
    if not isinstance(code, str) or len(code) != TOTP_DIGITS or not code.isascii() or not code.isdigit():
        return TotpVerification(accepted=False, reason="invalid_format")
    timestamp = time.time() if at_time is None else at_time
    if timestamp < 0:
        raise ValueError("at_time cannot be negative.")
    current_step = int(timestamp // TOTP_PERIOD_SECONDS)
    for offset in range(-allowed_window, allowed_window + 1):
        candidate_step = current_step + offset
        if candidate_step < 0:
            continue
        candidate = totp_code_for_step(secret, candidate_step)
        if hmac.compare_digest(candidate, code):
            if last_used_step is not None and candidate_step <= last_used_step:
                return TotpVerification(
                    accepted=False,
                    matched_step=candidate_step,
                    reason="replayed_step",
                )
            return TotpVerification(
                accepted=True,
                matched_step=candidate_step,
                reason="accepted",
            )
    return TotpVerification(accepted=False)


__all__ = [
    "TotpVerification",
    "build_totp_provisioning_uri",
    "encode_totp_secret",
    "generate_totp_secret",
    "totp_code_for_step",
    "verify_totp",
]
