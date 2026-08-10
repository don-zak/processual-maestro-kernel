"""Provider event inbox and tamper-evident evidence contracts for Stage 4.

The inbox normalizes externally supplied event evidence without performing any
provider network calls. Storage and production consumption remain disabled.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

PROVIDER_EVENT_INBOX_VERSION: Final = "2026-08-b4-provider-event-inbox-v1"
PROVIDER_EVENT_INBOX_STORAGE_ENABLED: Final = False
PROVIDER_EVENT_CONSUMPTION_ENABLED: Final = False
GENESIS_DIGEST: Final = "0" * 64


def canonical_payload_digest(payload: dict[str, object]) -> str:
    material = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderInboxEvent:
    provider_id: str
    external_event_id: str
    event_type: str
    occurred_at: datetime
    received_at: datetime
    payload_digest: str
    evidence_reference: str

    def __post_init__(self) -> None:
        for name, value in (
            ("provider_id", self.provider_id),
            ("external_event_id", self.external_event_id),
            ("event_type", self.event_type),
            ("evidence_reference", self.evidence_reference),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")
        if self.occurred_at.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("provider event timestamps must be timezone-aware")
        if self.received_at < self.occurred_at:
            raise ValueError("received_at must not be before occurred_at")
        if len(self.payload_digest) != 64:
            raise ValueError("payload_digest must be a sha256 hex digest")
        try:
            int(self.payload_digest, 16)
        except ValueError as exc:
            raise ValueError("payload_digest must be a sha256 hex digest") from exc

    @property
    def canonical_idempotency_key(self) -> str:
        return f"provider-event:{self.provider_id}:{self.external_event_id}"


def same_provider_event(left: ProviderInboxEvent, right: ProviderInboxEvent) -> bool:
    return (
        left.canonical_idempotency_key == right.canonical_idempotency_key
        and left.event_type == right.event_type
        and left.occurred_at == right.occurred_at
        and left.payload_digest == right.payload_digest
        and left.evidence_reference == right.evidence_reference
    )


def validate_provider_event_replay(
    existing: ProviderInboxEvent,
    incoming: ProviderInboxEvent,
) -> ProviderInboxEvent:
    if existing.canonical_idempotency_key != incoming.canonical_idempotency_key:
        raise ValueError("provider event replay key mismatch")
    if not same_provider_event(existing, incoming):
        raise ValueError("provider event replay conflicts with existing evidence")
    return existing


def provider_event_chain_digest(
    events: Iterable[ProviderInboxEvent],
    *,
    genesis_digest: str = GENESIS_DIGEST,
) -> str:
    if len(genesis_digest) != 64:
        raise ValueError("genesis_digest must be a sha256 hex digest")
    previous = genesis_digest
    for event in events:
        material = "|".join(
            (
                previous,
                event.canonical_idempotency_key,
                event.event_type,
                event.occurred_at.isoformat(),
                event.payload_digest,
                event.evidence_reference,
            )
        )
        previous = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return previous


def build_provider_event_inbox_status() -> dict[str, object]:
    return {
        "version": PROVIDER_EVENT_INBOX_VERSION,
        "storage_enabled": PROVIDER_EVENT_INBOX_STORAGE_ENABLED,
        "consumption_enabled": PROVIDER_EVENT_CONSUMPTION_ENABLED,
        "unique_provider_external_event_required": True,
        "payload_digest_required": True,
        "tamper_evident_chain_supported": True,
    }


__all__ = [
    "GENESIS_DIGEST",
    "PROVIDER_EVENT_CONSUMPTION_ENABLED",
    "PROVIDER_EVENT_INBOX_STORAGE_ENABLED",
    "PROVIDER_EVENT_INBOX_VERSION",
    "ProviderInboxEvent",
    "build_provider_event_inbox_status",
    "canonical_payload_digest",
    "provider_event_chain_digest",
    "same_provider_event",
    "validate_provider_event_replay",
]
