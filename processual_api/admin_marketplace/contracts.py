from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from processual_api.admin_marketplace.errors import AdminMarketplaceError

_CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_COUNTRY_PATTERN = re.compile(r"^[A-Z]{2}$")


def _required_text(value: str, *, field_name: str, maximum: int = 255) -> str:
    normalized = value.strip()
    if not normalized:
        raise AdminMarketplaceError(f"{field_name} is required.")
    if len(normalized) > maximum:
        raise AdminMarketplaceError(f"{field_name} is too long.")
    return normalized


def _required_code(value: str, *, field_name: str) -> str:
    normalized = _required_text(value, field_name=field_name, maximum=128).lower()
    if not _CODE_PATTERN.fullmatch(normalized):
        raise AdminMarketplaceError(f"{field_name} is invalid.")
    return normalized


def _currency(value: str) -> str:
    normalized = value.strip().upper()
    if not _CURRENCY_PATTERN.fullmatch(normalized):
        raise AdminMarketplaceError("currency must be a three-letter ISO code.")
    return normalized


def _country(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    if not _COUNTRY_PATTERN.fullmatch(normalized):
        raise AdminMarketplaceError("country_code must be a two-letter ISO code.")
    return normalized


def _aware_datetime(value: datetime | None, *, field_name: str) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise AdminMarketplaceError(f"{field_name} must be timezone-aware.")
    return value


def _immutable_mapping(value: Mapping[str, str] | None) -> Mapping[str, str]:
    source = value or {}
    normalized: dict[str, str] = {}
    for key, item in source.items():
        normalized[_required_code(str(key), field_name="metadata key")] = _required_text(
            str(item), field_name="metadata value", maximum=512
        )
    return MappingProxyType(normalized)


def _enum_member(
    value: object,
    enum_type: type[StrEnum],
    *,
    field_name: str,
) -> StrEnum:
    if not isinstance(value, enum_type):
        raise AdminMarketplaceError(
            f"{field_name} must be a valid {enum_type.__name__}."
        )
    return value


def _finite_amount(
    value: Decimal,
    *,
    field_name: str = "amount",
) -> Decimal:
    if not isinstance(value, Decimal):
        raise AdminMarketplaceError(
            f"{field_name} must be a Decimal."
        )
    if not value.is_finite():
        raise AdminMarketplaceError(
            f"{field_name} must be finite."
        )
    if value < Decimal("0"):
        raise AdminMarketplaceError(
            f"{field_name} must not be negative."
        )
    return value


class OfferStatus(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class SubscriptionStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TrialStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CONVERTED = "converted"
    EXPIRED = "expired"
    REJECTED = "rejected"


class OrderStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    AWAITING_PAYMENT_VERIFICATION = "awaiting_payment_verification"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FULFILLED = "fulfilled"


class PaymentVerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REQUIRES_REVIEW = "requires_review"


class SalesChannel(StrEnum):
    MAESTRO_DIRECT = "maestro_direct"
    LEMON_SQUEEZY = "lemon_squeezy"


class ChannelEligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    REQUIRES_REVIEW = "requires_review"


class CommercialDecisionOutcome(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class CommercialPlanContract:
    plan_code: str
    display_name: str
    entitlement_profile_ref: str
    quota_profile_ref: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_code", _required_code(self.plan_code, field_name="plan_code"))
        object.__setattr__(self, "display_name", _required_text(self.display_name, field_name="display_name"))
        object.__setattr__(self, "entitlement_profile_ref", _required_code(self.entitlement_profile_ref, field_name="entitlement_profile_ref"))
        object.__setattr__(self, "quota_profile_ref", _required_code(self.quota_profile_ref, field_name="quota_profile_ref"))
        object.__setattr__(self, "metadata", _immutable_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class CommercialOfferContract:
    offer_code: str
    plan_code: str
    display_name: str
    currency: str
    amount: Decimal
    status: OfferStatus = OfferStatus.DRAFT
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    customer_specific: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "offer_code", _required_code(self.offer_code, field_name="offer_code"))
        object.__setattr__(self, "plan_code", _required_code(self.plan_code, field_name="plan_code"))
        object.__setattr__(self, "display_name", _required_text(self.display_name, field_name="display_name"))
        object.__setattr__(self, "currency", _currency(self.currency))
        object.__setattr__(
            self,
            "amount",
            _finite_amount(self.amount),
        )
        _enum_member(
            self.status,
            OfferStatus,
            field_name="status",
        )
        effective_at = _aware_datetime(self.effective_at, field_name="effective_at")
        expires_at = _aware_datetime(self.expires_at, field_name="expires_at")
        if effective_at and expires_at and expires_at <= effective_at:
            raise AdminMarketplaceError("expires_at must be later than effective_at.")


@dataclass(frozen=True, slots=True)
class CommercialSubscriptionContract:
    subscription_id: str
    customer_id: str
    offer_code: str
    plan_code: str
    status: SubscriptionStatus
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "subscription_id", _required_code(self.subscription_id, field_name="subscription_id"))
        object.__setattr__(self, "customer_id", _required_code(self.customer_id, field_name="customer_id"))
        object.__setattr__(self, "offer_code", _required_code(self.offer_code, field_name="offer_code"))
        object.__setattr__(self, "plan_code", _required_code(self.plan_code, field_name="plan_code"))
        _enum_member(
            self.status,
            SubscriptionStatus,
            field_name="status",
        )
        starts_at = _aware_datetime(self.starts_at, field_name="starts_at")
        ends_at = _aware_datetime(self.ends_at, field_name="ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise AdminMarketplaceError("ends_at must be later than starts_at.")


@dataclass(frozen=True, slots=True)
class CommercialTrialContract:
    trial_id: str
    customer_id: str
    plan_code: str
    status: TrialStatus
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trial_id", _required_code(self.trial_id, field_name="trial_id"))
        object.__setattr__(self, "customer_id", _required_code(self.customer_id, field_name="customer_id"))
        object.__setattr__(self, "plan_code", _required_code(self.plan_code, field_name="plan_code"))
        _enum_member(
            self.status,
            TrialStatus,
            field_name="status",
        )
        starts_at = _aware_datetime(self.starts_at, field_name="starts_at")
        ends_at = _aware_datetime(self.ends_at, field_name="ends_at")
        if starts_at and ends_at and ends_at <= starts_at:
            raise AdminMarketplaceError("ends_at must be later than starts_at.")


@dataclass(frozen=True, slots=True)
class CommercialOrderContract:
    order_id: str
    customer_id: str
    offer_code: str
    selected_channel: SalesChannel
    status: OrderStatus = OrderStatus.DRAFT

    def __post_init__(self) -> None:
        object.__setattr__(self, "order_id", _required_code(self.order_id, field_name="order_id"))
        object.__setattr__(self, "customer_id", _required_code(self.customer_id, field_name="customer_id"))
        object.__setattr__(self, "offer_code", _required_code(self.offer_code, field_name="offer_code"))
        _enum_member(
            self.selected_channel,
            SalesChannel,
            field_name="selected_channel",
        )
        _enum_member(
            self.status,
            OrderStatus,
            field_name="status",
        )


@dataclass(frozen=True, slots=True)
class PaymentVerificationContract:
    verification_id: str
    order_id: str
    status: PaymentVerificationStatus = PaymentVerificationStatus.PENDING
    safe_reference: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "verification_id", _required_code(self.verification_id, field_name="verification_id"))
        object.__setattr__(self, "order_id", _required_code(self.order_id, field_name="order_id"))
        _enum_member(
            self.status,
            PaymentVerificationStatus,
            field_name="status",
        )
        if self.safe_reference is not None:
            object.__setattr__(self, "safe_reference", _required_text(self.safe_reference, field_name="safe_reference"))


@dataclass(frozen=True, slots=True)
class CommercialInvoiceContract:
    invoice_id: str
    order_id: str
    currency: str
    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "invoice_id", _required_code(self.invoice_id, field_name="invoice_id"))
        object.__setattr__(self, "order_id", _required_code(self.order_id, field_name="order_id"))
        object.__setattr__(self, "currency", _currency(self.currency))
        object.__setattr__(
            self,
            "amount",
            _finite_amount(self.amount),
        )


@dataclass(frozen=True, slots=True)
class EntitlementActivationContract:
    activation_id: str
    customer_id: str
    subscription_id: str
    entitlement_profile_ref: str
    automatic_activation_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "activation_id", _required_code(self.activation_id, field_name="activation_id"))
        object.__setattr__(self, "customer_id", _required_code(self.customer_id, field_name="customer_id"))
        object.__setattr__(self, "subscription_id", _required_code(self.subscription_id, field_name="subscription_id"))
        object.__setattr__(self, "entitlement_profile_ref", _required_code(self.entitlement_profile_ref, field_name="entitlement_profile_ref"))


@dataclass(frozen=True, slots=True)
class SalesChannelEligibilityContract:
    country_code: str | None
    maestro_direct_status: ChannelEligibilityStatus
    lemon_squeezy_status: ChannelEligibilityStatus
    customer_choice_allowed: bool
    admin_review_required: bool
    restriction_reason: str | None = None
    automatic_activation_allowed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "country_code", _country(self.country_code))
        _enum_member(
            self.maestro_direct_status,
            ChannelEligibilityStatus,
            field_name="maestro_direct_status",
        )
        _enum_member(
            self.lemon_squeezy_status,
            ChannelEligibilityStatus,
            field_name="lemon_squeezy_status",
        )
        if self.restriction_reason is not None:
            object.__setattr__(self, "restriction_reason", _required_text(self.restriction_reason, field_name="restriction_reason"))

        restricted = ChannelEligibilityStatus.INELIGIBLE in {
            self.maestro_direct_status,
            self.lemon_squeezy_status,
        }
        review = ChannelEligibilityStatus.REQUIRES_REVIEW in {
            self.maestro_direct_status,
            self.lemon_squeezy_status,
        }
        if restricted and not self.restriction_reason:
            raise AdminMarketplaceError("restriction_reason is required when a sales channel is ineligible.")
        if review and not self.admin_review_required:
            raise AdminMarketplaceError("admin_review_required must be true when channel eligibility requires review.")
        if self.admin_review_required and self.automatic_activation_allowed:
            raise AdminMarketplaceError("automatic activation is forbidden while administrator review is required.")
        if self.customer_choice_allowed:
            eligible_count = sum(
                status is ChannelEligibilityStatus.ELIGIBLE
                for status in (self.maestro_direct_status, self.lemon_squeezy_status)
            )
            if eligible_count < 2:
                raise AdminMarketplaceError("customer choice requires at least two eligible sales channels.")


@dataclass(frozen=True, slots=True)
class CustomerChannelSelectionContract:
    customer_id: str
    selected_channel: SalesChannel
    eligible_channels: frozenset[SalesChannel]
    customer_consented: bool = True
    administrator_override_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "customer_id", _required_code(self.customer_id, field_name="customer_id"))
        _enum_member(
            self.selected_channel,
            SalesChannel,
            field_name="selected_channel",
        )

        normalized_channels = frozenset(self.eligible_channels)
        if not all(
            isinstance(channel, SalesChannel)
            for channel in normalized_channels
        ):
            raise AdminMarketplaceError(
                "eligible_channels must contain only valid "
                "SalesChannel values."
            )

        object.__setattr__(
            self,
            "eligible_channels",
            normalized_channels,
        )

        if self.selected_channel not in self.eligible_channels:
            raise AdminMarketplaceError("selected_channel must be eligible.")
        if not self.customer_consented and not self.administrator_override_reason:
            raise AdminMarketplaceError("a documented administrator override is required without customer consent.")
        if self.administrator_override_reason is not None:
            object.__setattr__(self, "administrator_override_reason", _required_text(self.administrator_override_reason, field_name="administrator_override_reason"))


@dataclass(frozen=True, slots=True)
class CommercialDecisionContract:
    decision_id: str
    action: str
    resource_type: str
    resource_id: str
    outcome: CommercialDecisionOutcome
    reason_code: str

    def __post_init__(self) -> None:
        for field_name in ("decision_id", "action", "resource_type", "resource_id", "reason_code"):
            object.__setattr__(
                self,
                field_name,
                _required_code(
                    getattr(self, field_name),
                    field_name=field_name,
                ),
            )

        _enum_member(
            self.outcome,
            CommercialDecisionOutcome,
            field_name="outcome",
        )


__all__ = [
    "ChannelEligibilityStatus",
    "CommercialDecisionContract",
    "CommercialDecisionOutcome",
    "CommercialInvoiceContract",
    "CommercialOfferContract",
    "CommercialOrderContract",
    "CommercialPlanContract",
    "CommercialSubscriptionContract",
    "CommercialTrialContract",
    "CustomerChannelSelectionContract",
    "EntitlementActivationContract",
    "OfferStatus",
    "OrderStatus",
    "PaymentVerificationContract",
    "PaymentVerificationStatus",
    "SalesChannel",
    "SalesChannelEligibilityContract",
    "SubscriptionStatus",
    "TrialStatus",
]
