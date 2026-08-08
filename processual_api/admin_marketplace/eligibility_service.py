from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAction,
    AdminMarketplaceAuthorityContext,
    require_admin_marketplace_authority,
)
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
)

TUNISIA_COUNTRY_CODE = "TN"
ELIGIBLE_CHANNEL_STATUS = "eligible"
INELIGIBLE_CHANNEL_STATUS = "ineligible"
REQUIRES_REVIEW_CHANNEL_STATUS = "requires_review"


class AdminMarketplaceEligibilityState(StrEnum):
    ELIGIBLE = "eligible"
    ELIGIBILITY_NOT_FOUND = "eligibility_not_found"
    ADDRESS_NOT_CONFIRMED = "address_not_confirmed"
    NON_TUNISIAN = "non_tunisian"
    MAESTRO_DIRECT_INELIGIBLE = "maestro_direct_ineligible"
    MAESTRO_DIRECT_REQUIRES_REVIEW = "maestro_direct_requires_review"
    INVALID_ELIGIBILITY_STATE = "invalid_eligibility_state"


@dataclass(frozen=True, slots=True)
class AdminMarketplaceEligibilityResult:
    customer_ref: str
    state: AdminMarketplaceEligibilityState
    visible: bool
    country_code: str | None
    address_status: str | None
    maestro_direct_status: str | None
    admin_review_required: bool
    reason_code: str


class AdminMarketplaceEligibilityService:
    """Read-only composition of marketplace authority and stored eligibility."""

    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], AdminMarketplaceUnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def evaluate(
        self,
        *,
        authority: AdminMarketplaceAuthorityContext,
        customer_ref: str,
    ) -> AdminMarketplaceEligibilityResult:
        normalized_customer_ref = customer_ref.strip()
        if not normalized_customer_ref:
            raise ValueError("customer_ref must not be blank.")

        require_admin_marketplace_authority(
            context=authority,
            action=AdminMarketplaceAction.VIEW_CATALOG,
        )

        async with self._unit_of_work_factory() as unit:
            eligibility = await unit.channel_eligibilities.get_by_customer_ref(
                normalized_customer_ref,
            )

        if eligibility is None:
            return AdminMarketplaceEligibilityResult(
                customer_ref=normalized_customer_ref,
                state=AdminMarketplaceEligibilityState.ELIGIBILITY_NOT_FOUND,
                visible=False,
                country_code=None,
                address_status=None,
                maestro_direct_status=None,
                admin_review_required=False,
                reason_code="channel_eligibility_record_required",
            )

        country_code = eligibility.country_code.strip().upper() if eligibility.country_code is not None else None
        address_status = str(
            getattr(eligibility, "address_status", "unverified")
        ).strip().lower()
        maestro_direct_status = eligibility.maestro_direct_status.strip().lower()
        admin_review_required = bool(eligibility.admin_review_required)

        if address_status != "confirmed":
            return AdminMarketplaceEligibilityResult(
                customer_ref=normalized_customer_ref,
                state=AdminMarketplaceEligibilityState.ADDRESS_NOT_CONFIRMED,
                visible=False,
                country_code=country_code,
                address_status=address_status,
                maestro_direct_status=maestro_direct_status,
                admin_review_required=admin_review_required,
                reason_code="confirmed_customer_address_required",
            )

        if country_code != TUNISIA_COUNTRY_CODE:
            return AdminMarketplaceEligibilityResult(
                customer_ref=normalized_customer_ref,
                state=AdminMarketplaceEligibilityState.NON_TUNISIAN,
                visible=False,
                country_code=country_code,
                address_status=address_status,
                maestro_direct_status=maestro_direct_status,
                admin_review_required=admin_review_required,
                reason_code="tunisian_customer_required",
            )

        if maestro_direct_status == REQUIRES_REVIEW_CHANNEL_STATUS or admin_review_required:
            return AdminMarketplaceEligibilityResult(
                customer_ref=normalized_customer_ref,
                state=(AdminMarketplaceEligibilityState.MAESTRO_DIRECT_REQUIRES_REVIEW),
                visible=False,
                country_code=country_code,
                address_status=address_status,
                maestro_direct_status=maestro_direct_status,
                admin_review_required=admin_review_required,
                reason_code="maestro_direct_admin_review_required",
            )

        if maestro_direct_status == INELIGIBLE_CHANNEL_STATUS:
            return AdminMarketplaceEligibilityResult(
                customer_ref=normalized_customer_ref,
                state=(AdminMarketplaceEligibilityState.MAESTRO_DIRECT_INELIGIBLE),
                visible=False,
                country_code=country_code,
                address_status=address_status,
                maestro_direct_status=maestro_direct_status,
                admin_review_required=admin_review_required,
                reason_code=(eligibility.restriction_reason or "maestro_direct_channel_ineligible"),
            )

        if maestro_direct_status != ELIGIBLE_CHANNEL_STATUS:
            return AdminMarketplaceEligibilityResult(
                customer_ref=normalized_customer_ref,
                state=AdminMarketplaceEligibilityState.INVALID_ELIGIBILITY_STATE,
                visible=False,
                country_code=country_code,
                address_status=address_status,
                maestro_direct_status=maestro_direct_status,
                admin_review_required=admin_review_required,
                reason_code="invalid_maestro_direct_eligibility_state",
            )

        return AdminMarketplaceEligibilityResult(
            customer_ref=normalized_customer_ref,
            state=AdminMarketplaceEligibilityState.ELIGIBLE,
            visible=True,
            country_code=country_code,
            address_status=address_status,
            maestro_direct_status=maestro_direct_status,
            admin_review_required=False,
            reason_code="tunisian_maestro_direct_eligible",
        )


__all__ = [
    "AdminMarketplaceEligibilityResult",
    "AdminMarketplaceEligibilityService",
    "AdminMarketplaceEligibilityState",
    "TUNISIA_COUNTRY_CODE",
]
