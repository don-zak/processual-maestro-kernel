from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from processual_api.admin_marketplace.errors import AdminMarketplaceAuditSafetyError

_PROHIBITED_KEY_PATTERN = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|cookie|credential|mfa|otp|webhook[_-]?signature|payment[_-]?evidence)",
    re.IGNORECASE,
)
_DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class CommercialAuditAction(StrEnum):
    AUTHORITY_CHECKED = "authority_checked"
    OFFER_DECIDED = "offer_decided"
    CHANNEL_ELIGIBILITY_DECIDED = "channel_eligibility_decided"
    CHANNEL_SELECTED = "channel_selected"
    PAYMENT_VERIFICATION_DECIDED = "payment_verification_decided"
    SUBSCRIPTION_ACTIVATION_DECIDED = "subscription_activation_decided"
    PAYMENT_DESTINATION_CREATED = "payment_destination_created"
    PAYMENT_DESTINATION_VALIDATED = "payment_destination_validated"
    PAYMENT_DESTINATION_ACTIVATED = "payment_destination_activated"
    PAYMENT_DESTINATION_DEACTIVATED = "payment_destination_deactivated"
    PAYMENT_DESTINATION_DEFAULT_SET = "payment_destination_default_set"


class CommercialResourceType(StrEnum):
    OFFER = "offer"
    PLAN = "plan"
    ORDER = "order"
    PAYMENT_VERIFICATION = "payment_verification"
    SUBSCRIPTION = "subscription"
    TRIAL = "trial"
    SALES_CHANNEL_ELIGIBILITY = "sales_channel_eligibility"
    PAYMENT_DESTINATION = "payment_destination"


class CommercialAuditOutcome(StrEnum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_REVIEW = "requires_review"


def _required(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AdminMarketplaceAuditSafetyError(f"{field_name} is required.")
    return normalized


def _safe_metadata(metadata: Mapping[str, str] | None) -> Mapping[str, str]:
    normalized: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        key_text = _required(str(key), field_name="metadata key")
        if _PROHIBITED_KEY_PATTERN.search(key_text):
            raise AdminMarketplaceAuditSafetyError(f"Sensitive audit metadata key is forbidden: {key_text}")
        value_text = _required(str(value), field_name="metadata value")
        if len(value_text) > 1024:
            raise AdminMarketplaceAuditSafetyError("Audit metadata value is too long.")
        normalized[key_text] = value_text
    return MappingProxyType(normalized)


def _digest(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not _DIGEST_PATTERN.fullmatch(normalized):
        raise AdminMarketplaceAuditSafetyError(f"{field_name} must be a SHA-256 hex digest.")
    return normalized


@dataclass(frozen=True, slots=True)
class CommercialAuditRecord:
    event_id: str
    occurred_at: datetime
    actor_user_id: str
    actor_session_id: str
    platform_authority: str
    action: CommercialAuditAction
    resource_type: CommercialResourceType
    resource_id: str
    outcome: CommercialAuditOutcome
    reason_code: str
    correlation_id: str
    previous_state_digest: str | None = None
    new_state_digest: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "actor_user_id",
            "actor_session_id",
            "platform_authority",
            "resource_id",
            "reason_code",
            "correlation_id",
        ):
            object.__setattr__(self, field_name, _required(getattr(self, field_name), field_name=field_name))
        if self.occurred_at.tzinfo is None:
            raise AdminMarketplaceAuditSafetyError("occurred_at must be timezone-aware.")
        if not isinstance(self.action, CommercialAuditAction):
            raise AdminMarketplaceAuditSafetyError("action must be a valid CommercialAuditAction.")
        if not isinstance(self.resource_type, CommercialResourceType):
            raise AdminMarketplaceAuditSafetyError("resource_type must be a valid CommercialResourceType.")
        if not isinstance(self.outcome, CommercialAuditOutcome):
            raise AdminMarketplaceAuditSafetyError("outcome must be a valid CommercialAuditOutcome.")
        if self.platform_authority != "platform_admin":
            raise AdminMarketplaceAuditSafetyError("Commercial audit actor must use platform_admin authority.")
        object.__setattr__(
            self, "previous_state_digest", _digest(self.previous_state_digest, field_name="previous_state_digest")
        )
        object.__setattr__(self, "new_state_digest", _digest(self.new_state_digest, field_name="new_state_digest"))
        object.__setattr__(self, "metadata", _safe_metadata(self.metadata))


__all__ = [
    "CommercialAuditAction",
    "CommercialAuditOutcome",
    "CommercialAuditRecord",
    "CommercialResourceType",
]
