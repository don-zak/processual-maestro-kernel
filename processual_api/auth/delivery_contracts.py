from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DeliveryClaim:
    outbox_id: uuid.UUID
    user_id: uuid.UUID
    action_token_id: uuid.UUID
    claim_id: uuid.UUID
    recipient_email: str
    user_status: str
    event_type: str
    payload_ciphertext: bytes
    payload_key_version: str
    action_token_expires_at: datetime
    action_token_consumed_at: datetime | None
    action_token_invalidated_at: datetime | None
    attempt_count: int


__all__ = ["DeliveryClaim"]
