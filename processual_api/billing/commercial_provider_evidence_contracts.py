"""Observe-only provider event and payment evidence contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from hmac import compare_digest
from typing import Final

PROVIDER_EVIDENCE_VERSION: Final = "2026-07-group2-provider-evidence-v1"
PROVIDER_EVIDENCE_STATUS: Final = "draft_review"
PROVIDER_WEBHOOK_RUNTIME_ENABLED: Final = False
PROVIDER_EVENT_WRITES_ENABLED: Final = False
PROVIDER_DIRECT_GRANT_ALLOWED: Final = False
PROVIDER_SECRET_LOGGING_ALLOWED: Final = False


class ProviderChannel(StrEnum):
    LEMON_SQUEEZY = "lemon_squeezy"
    LOCAL_TUNISIA = "local_tunisia"


class ProviderEvidenceState(StrEnum):
    OBSERVED = "observed"
    SIGNATURE_VERIFIED = "signature_verified"
    REPLAY_REJECTED = "replay_rejected"
    INVALID_SIGNATURE = "invalid_signature"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class ProviderEventEnvelope:
    provider_channel: ProviderChannel
    provider_event_reference: str
    provider_payment_reference: str
    occurred_at: datetime
    received_at: datetime
    payload_digest: str
    signature_digest: str
    replay_key: str

    def __post_init__(self) -> None:
        for name, value in (
            ("provider_event_reference", self.provider_event_reference),
            ("provider_payment_reference", self.provider_payment_reference),
            ("payload_digest", self.payload_digest),
            ("signature_digest", self.signature_digest),
            ("replay_key", self.replay_key),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        if self.received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")
        if len(self.payload_digest) != 64:
            raise ValueError("payload_digest must be SHA-256 hex")
        if len(self.signature_digest) != 64:
            raise ValueError("signature_digest must be SHA-256 hex")

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderEvidenceDecision:
    state: ProviderEvidenceState
    accepted_as_evidence: bool
    grant_allowed: bool
    runtime_write_allowed: bool
    reason: str

    def __post_init__(self) -> None:
        if self.grant_allowed:
            raise ValueError("provider evidence must never grant units directly")
        if self.runtime_write_allowed:
            raise ValueError("provider event runtime writes remain disabled")


def digest_payload(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def digest_signature(signature: str) -> str:
    if not signature.strip():
        raise ValueError("signature must not be blank")
    return sha256(signature.encode("utf-8")).hexdigest()


def verify_digest(
    *,
    expected_digest: str,
    observed_digest: str,
) -> bool:
    if len(expected_digest) != 64 or len(observed_digest) != 64:
        return False
    return compare_digest(expected_digest, observed_digest)


def decide_provider_evidence(
    *,
    signature_valid: bool,
    replay_detected: bool,
) -> ProviderEvidenceDecision:
    if replay_detected:
        return ProviderEvidenceDecision(
            state=ProviderEvidenceState.REPLAY_REJECTED,
            accepted_as_evidence=False,
            grant_allowed=False,
            runtime_write_allowed=False,
            reason="provider replay key was already observed",
        )
    if not signature_valid:
        return ProviderEvidenceDecision(
            state=ProviderEvidenceState.INVALID_SIGNATURE,
            accepted_as_evidence=False,
            grant_allowed=False,
            runtime_write_allowed=False,
            reason="provider signature verification failed",
        )
    return ProviderEvidenceDecision(
        state=ProviderEvidenceState.SIGNATURE_VERIFIED,
        accepted_as_evidence=True,
        grant_allowed=False,
        runtime_write_allowed=False,
        reason=(
            "provider event may be recorded as evidence only; commercial verification and activation remain separate"
        ),
    )


def build_provider_evidence_status() -> dict[str, object]:
    return {
        "version": PROVIDER_EVIDENCE_VERSION,
        "status": PROVIDER_EVIDENCE_STATUS,
        "webhook_runtime_enabled": PROVIDER_WEBHOOK_RUNTIME_ENABLED,
        "event_writes_enabled": PROVIDER_EVENT_WRITES_ENABLED,
        "direct_grant_allowed": PROVIDER_DIRECT_GRANT_ALLOWED,
        "secret_logging_allowed": PROVIDER_SECRET_LOGGING_ALLOWED,
        "signature_verification_required": True,
        "replay_protection_required": True,
        "immutable_evidence_reference_required": True,
        "payment_verification_required_after_evidence": True,
        "platform_admin_activation_required": True,
    }


__all__ = [
    "PROVIDER_DIRECT_GRANT_ALLOWED",
    "PROVIDER_EVENT_WRITES_ENABLED",
    "PROVIDER_EVIDENCE_STATUS",
    "PROVIDER_EVIDENCE_VERSION",
    "PROVIDER_SECRET_LOGGING_ALLOWED",
    "PROVIDER_WEBHOOK_RUNTIME_ENABLED",
    "ProviderChannel",
    "ProviderEventEnvelope",
    "ProviderEvidenceDecision",
    "ProviderEvidenceState",
    "build_provider_evidence_status",
    "decide_provider_evidence",
    "digest_payload",
    "digest_signature",
    "verify_digest",
]
