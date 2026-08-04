from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from processual_api.admin_marketplace.errors import AdminMarketplaceError

TUNISIA_COUNTRY_CODE = "TN"
TUNISIAN_DINAR_CURRENCY = "TND"

_IDENTIFIER_PATTERN = re.compile(r"^[A-Z0-9]{8,64}$")
_DISPLAY_NAME_PATTERN = re.compile(r"^[^\x00-\x1f\x7f]{2,120}$")


class PaymentDestinationType(StrEnum):
    BANK_ACCOUNT = "bank_account"
    POSTAL_ACCOUNT = "postal_account"


class PaymentDestinationStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    INACTIVE = "inactive"


class PaymentDestinationValidationMethod(StrEnum):
    STRUCTURAL = "structural"
    PROVIDER = "provider"


@dataclass(frozen=True, slots=True)
class PaymentDestinationCreateContract:
    destination_ref: str
    display_name: str
    destination_type: PaymentDestinationType
    institution_name: str
    account_holder_name: str
    raw_account_identifier: str
    instructions: str | None = None

    def __post_init__(self) -> None:
        destination_ref = self.destination_ref.strip().lower()
        display_name = self.display_name.strip()
        institution_name = self.institution_name.strip()
        account_holder_name = self.account_holder_name.strip()
        raw_identifier = self.raw_account_identifier.strip()

        if not destination_ref:
            raise AdminMarketplaceError("destination_ref is required.")
        if not _DISPLAY_NAME_PATTERN.fullmatch(display_name):
            raise AdminMarketplaceError("display_name is invalid.")
        if not institution_name or len(institution_name) > 160:
            raise AdminMarketplaceError("institution_name is invalid.")
        if not account_holder_name or len(account_holder_name) > 160:
            raise AdminMarketplaceError("account_holder_name is invalid.")
        if not raw_identifier:
            raise AdminMarketplaceError("raw_account_identifier is required.")
        if not isinstance(self.destination_type, PaymentDestinationType):
            raise AdminMarketplaceError("destination_type is invalid.")

        object.__setattr__(self, "destination_ref", destination_ref)
        object.__setattr__(self, "display_name", display_name)
        object.__setattr__(self, "institution_name", institution_name)
        object.__setattr__(self, "account_holder_name", account_holder_name)
        object.__setattr__(self, "raw_account_identifier", raw_identifier)
        object.__setattr__(
            self,
            "instructions",
            self.instructions.strip() if self.instructions else None,
        )


@dataclass(frozen=True, slots=True)
class PaymentDestinationValidationResult:
    valid: bool
    normalized_identifier: str | None
    masked_identifier: str | None
    method: PaymentDestinationValidationMethod
    reason_code: str


def normalize_payment_identifier(value: str) -> str:
    normalized = "".join(character for character in value.upper() if character.isalnum())
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise AdminMarketplaceError("payment destination identifier is invalid.")
    return normalized


def mask_payment_identifier(value: str) -> str:
    normalized = normalize_payment_identifier(value)
    visible_suffix = normalized[-4:]
    hidden_length = max(4, len(normalized) - len(visible_suffix))
    return f"{'*' * hidden_length}{visible_suffix}"


def validate_payment_destination_identifier(
    *,
    value: str,
    destination_type: PaymentDestinationType,
) -> PaymentDestinationValidationResult:
    try:
        normalized = normalize_payment_identifier(value)
    except AdminMarketplaceError:
        return PaymentDestinationValidationResult(
            valid=False,
            normalized_identifier=None,
            masked_identifier=None,
            method=PaymentDestinationValidationMethod.STRUCTURAL,
            reason_code="identifier_format_invalid",
        )

    if destination_type is PaymentDestinationType.BANK_ACCOUNT:
        minimum_length = 20
    elif destination_type is PaymentDestinationType.POSTAL_ACCOUNT:
        minimum_length = 8
    else:
        return PaymentDestinationValidationResult(
            valid=False,
            normalized_identifier=None,
            masked_identifier=None,
            method=PaymentDestinationValidationMethod.STRUCTURAL,
            reason_code="destination_type_invalid",
        )

    if len(normalized) < minimum_length:
        return PaymentDestinationValidationResult(
            valid=False,
            normalized_identifier=normalized,
            masked_identifier=mask_payment_identifier(normalized),
            method=PaymentDestinationValidationMethod.STRUCTURAL,
            reason_code="identifier_length_invalid",
        )

    return PaymentDestinationValidationResult(
        valid=True,
        normalized_identifier=normalized,
        masked_identifier=mask_payment_identifier(normalized),
        method=PaymentDestinationValidationMethod.STRUCTURAL,
        reason_code="structurally_validated",
    )


__all__ = [
    "PaymentDestinationCreateContract",
    "PaymentDestinationStatus",
    "PaymentDestinationType",
    "PaymentDestinationValidationMethod",
    "PaymentDestinationValidationResult",
    "TUNISIA_COUNTRY_CODE",
    "TUNISIAN_DINAR_CURRENCY",
    "mask_payment_identifier",
    "normalize_payment_identifier",
    "validate_payment_destination_identifier",
]
