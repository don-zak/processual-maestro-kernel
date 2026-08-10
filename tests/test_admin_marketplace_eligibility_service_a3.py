from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from processual_api.admin_marketplace.authority import authority_context
from processual_api.admin_marketplace.eligibility_service import (
    AdminMarketplaceEligibilityService,
    AdminMarketplaceEligibilityState,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
)


class FakeChannelEligibilityRepository:
    def __init__(self, eligibility=None) -> None:
        self.eligibility = eligibility
        self.customer_refs: list[str] = []

    async def get_by_customer_ref(
        self,
        customer_ref: str,
        *,
        for_update: bool = False,
    ):
        assert for_update is False
        self.customer_refs.append(customer_ref)
        return self.eligibility


class FakeUnitOfWork:
    def __init__(self, repository: FakeChannelEligibilityRepository) -> None:
        self.channel_eligibilities = repository
        self.entered = False
        self.exited = False
        self.commit_calls = 0

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        self.exited = True

    async def commit(self) -> None:
        self.commit_calls += 1

    async def rollback(self) -> None:
        pass


def _authority(*authorities: str, active: bool = True):
    return authority_context(
        user_id="admin_001",
        session_id="session_001",
        platform_authorities=authorities,
        active_platform_admin=active,
        recent_mfa_step_up=False,
    )


def _eligibility(
    *,
    country_code: str | None = "TN",
    address_status: str = "confirmed",
    maestro_direct_status: str = "eligible",
    admin_review_required: bool = False,
    restriction_reason: str | None = None,
):
    return SimpleNamespace(
        country_code=country_code,
        address_status=address_status,
        maestro_direct_status=maestro_direct_status,
        admin_review_required=admin_review_required,
        restriction_reason=restriction_reason,
    )


def _service(eligibility=None):
    repository = FakeChannelEligibilityRepository(eligibility)
    unit = FakeUnitOfWork(repository)
    service = AdminMarketplaceEligibilityService(
        unit_of_work_factory=lambda: unit,
    )
    return service, repository, unit


@pytest.mark.asyncio
async def test_tunisian_maestro_direct_customer_is_visible() -> None:
    service, repository, unit = _service(_eligibility())

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref=" customer_001 ",
    )

    assert result.state is AdminMarketplaceEligibilityState.ELIGIBLE
    assert result.visible is True
    assert result.country_code == "TN"
    assert result.reason_code == "tunisian_maestro_direct_eligible"
    assert repository.customer_refs == ["customer_001"]
    assert unit.entered is True
    assert unit.exited is True
    assert unit.commit_calls == 0


@pytest.mark.asyncio
async def test_missing_eligibility_record_is_hidden() -> None:
    service, _, unit = _service()

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.state is AdminMarketplaceEligibilityState.ELIGIBILITY_NOT_FOUND
    assert result.visible is False
    assert result.reason_code == "channel_eligibility_record_required"
    assert unit.commit_calls == 0


@pytest.mark.asyncio
async def test_unconfirmed_address_is_hidden_even_when_country_is_tunisia() -> None:
    service, _, _ = _service(_eligibility(address_status="unverified"))

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.state is AdminMarketplaceEligibilityState.ADDRESS_NOT_CONFIRMED
    assert result.visible is False
    assert result.address_status == "unverified"
    assert result.reason_code == "confirmed_customer_address_required"


@pytest.mark.asyncio
async def test_non_tunisian_customer_is_hidden() -> None:
    service, _, _ = _service(_eligibility(country_code="FR"))

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.state is AdminMarketplaceEligibilityState.NON_TUNISIAN
    assert result.visible is False
    assert result.reason_code == "tunisian_customer_required"


@pytest.mark.asyncio
async def test_ineligible_maestro_direct_customer_is_hidden() -> None:
    service, _, _ = _service(
        _eligibility(
            maestro_direct_status="ineligible",
            restriction_reason="unsupported_local_billing_profile",
        )
    )

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.state is AdminMarketplaceEligibilityState.MAESTRO_DIRECT_INELIGIBLE
    assert result.visible is False
    assert result.reason_code == "unsupported_local_billing_profile"


@pytest.mark.asyncio
async def test_review_required_customer_is_hidden() -> None:
    service, _, _ = _service(
        _eligibility(
            maestro_direct_status="requires_review",
            admin_review_required=True,
        )
    )

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.state is AdminMarketplaceEligibilityState.MAESTRO_DIRECT_REQUIRES_REVIEW
    assert result.visible is False
    assert result.reason_code == "maestro_direct_admin_review_required"


@pytest.mark.asyncio
async def test_admin_review_flag_fails_closed_even_when_channel_is_eligible() -> None:
    service, _, _ = _service(
        _eligibility(
            maestro_direct_status="eligible",
            admin_review_required=True,
        )
    )

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.state is AdminMarketplaceEligibilityState.MAESTRO_DIRECT_REQUIRES_REVIEW
    assert result.visible is False


@pytest.mark.asyncio
async def test_non_platform_admin_is_denied_before_repository_access() -> None:
    service, repository, unit = _service(_eligibility())

    with pytest.raises(AdminMarketplaceAuthorityDeniedError):
        await service.evaluate(
            authority=_authority("billing_admin"),
            customer_ref="customer_001",
        )

    assert repository.customer_refs == []
    assert unit.entered is False


@pytest.mark.asyncio
async def test_view_catalog_does_not_require_recent_mfa_step_up() -> None:
    service, _, _ = _service(_eligibility())

    result = await service.evaluate(
        authority=_authority("platform_admin"),
        customer_ref="customer_001",
    )

    assert result.visible is True


@pytest.mark.asyncio
async def test_blank_customer_reference_is_rejected_before_unit_of_work() -> None:
    repository = FakeChannelEligibilityRepository(_eligibility())
    factory = MagicMock()
    service = AdminMarketplaceEligibilityService(
        unit_of_work_factory=factory,
    )

    with pytest.raises(ValueError, match="customer_ref"):
        await service.evaluate(
            authority=_authority("platform_admin"),
            customer_ref="   ",
        )

    factory.assert_not_called()
    assert repository.customer_refs == []
