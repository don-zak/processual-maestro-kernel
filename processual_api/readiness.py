"""Operational readiness invariants that do not require external providers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    ok: bool
    status: str
    detail: str = ""


_REQUIRED_ENVELOPE_FIELDS = {
    "algorithm",
    "key_id",
    "nonce_b64",
    "ciphertext_b64",
    "plaintext_sha3_256",
    "ciphertext_sha3_256",
    "schema_version",
}
_FORBIDDEN_TOP_LEVEL_SECRET_FIELDS = {"api_key", "secret", "token", "password"}


def check_adapter_config_integrity(path: Path) -> ReadinessCheck:
    """Validate adapter persistence without contacting any external provider.

    The adapter configuration is optional. When present, it must be valid JSON,
    must never contain obvious plaintext secret fields, and any encrypted
    credential envelope must be structurally complete.
    """
    if not path.exists():
        return ReadinessCheck(True, "not_configured")

    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return ReadinessCheck(False, "invalid_json", type(exc).__name__)

    if not isinstance(payload, dict):
        return ReadinessCheck(False, "invalid_shape", "adapter config must be a JSON object")

    forbidden = sorted(_FORBIDDEN_TOP_LEVEL_SECRET_FIELDS.intersection(payload))
    if forbidden:
        return ReadinessCheck(False, "plaintext_secret_field", ",".join(forbidden))

    provider = payload.get("provider")
    if provider is not None and not isinstance(provider, str):
        return ReadinessCheck(False, "invalid_provider", "provider must be a string")

    encrypted_key = payload.get("encrypted_key")
    if encrypted_key is None:
        return ReadinessCheck(True, "metadata_only")
    if not isinstance(encrypted_key, str) or not encrypted_key.strip():
        return ReadinessCheck(False, "invalid_encrypted_key", "encrypted_key must be a non-empty JSON string")

    try:
        envelope = json.loads(encrypted_key)
    except json.JSONDecodeError as exc:
        return ReadinessCheck(False, "invalid_envelope_json", type(exc).__name__)

    if not isinstance(envelope, dict):
        return ReadinessCheck(False, "invalid_envelope_shape", "encrypted envelope must be a JSON object")

    missing = sorted(_REQUIRED_ENVELOPE_FIELDS.difference(envelope))
    if missing:
        return ReadinessCheck(False, "incomplete_envelope", ",".join(missing))

    if not envelope.get("ciphertext_b64") or not envelope.get("nonce_b64"):
        return ReadinessCheck(False, "empty_ciphertext", "ciphertext and nonce must be non-empty")

    return ReadinessCheck(True, "encrypted")
