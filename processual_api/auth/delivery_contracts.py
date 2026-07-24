from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DeliveryClaim:
    outbox_id: uuid.UUID
    user_id: uuid.UUID
    action_token_id: uuid.UUID | None
    claim_id: uuid.UUID
    recipient_email: str | None
    user_status: str
    event_type: str
    payload_ciphertext: bytes
    payload_key_version: str
    action_token_expires_at: datetime | None
    action_token_consumed_at: datetime | None
    action_token_invalidated_at: datetime | None
    attempt_count: int
    account_recovery_request_id: uuid.UUID | None = None
    account_recovery_expires_at: datetime | None = None
    account_recovery_state: str | None = None
    account_recovery_revoked_at: datetime | None = None

    @property
    def authority_id(self) -> uuid.UUID:
        if self.action_token_id is not None:
            return self.action_token_id
        if self.account_recovery_request_id is not None:
            return self.account_recovery_request_id
        raise ValueError("Delivery claim authority is unavailable.")

    @property
    def authority_expires_at(self) -> datetime | None:
        if self.action_token_id is not None:
            return self.action_token_expires_at
        return self.account_recovery_expires_at


__all__ = ["DeliveryClaim"]
