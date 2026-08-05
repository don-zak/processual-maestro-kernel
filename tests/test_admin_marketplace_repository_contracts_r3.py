from __future__ import annotations

import inspect

import pytest

from processual_api.admin_marketplace.persistence import errors
from processual_api.admin_marketplace.persistence.protocols import (
    AdminMarketplaceUnitOfWork,
    ChannelEligibilityRepository,
    ChannelSelectionRepository,
    CommercialAuditRepository,
    CommercialDecisionRepository,
    ContractRepository,
    EntitlementActivationRepository,
    InvoiceRepository,
    OfferRepository,
    OrderRepository,
    PaymentVerificationRepository,
    PlanRepository,
    SubscriptionRepository,
    TrialRepository,
)

REPOSITORY_PROTOCOLS = (
    PlanRepository,
    OfferRepository,
    SubscriptionRepository,
    TrialRepository,
    OrderRepository,
    ContractRepository,
    PaymentVerificationRepository,
    InvoiceRepository,
    EntitlementActivationRepository,
    ChannelEligibilityRepository,
    ChannelSelectionRepository,
    CommercialDecisionRepository,
    CommercialAuditRepository,
)

TRANSACTION_METHODS = {
    "begin",
    "close",
    "commit",
    "create_session",
    "rollback",
}

AUTOMATIC_ACTIVATION_METHODS = {
    "activate_after_payment",
    "activate_entitlements",
    "activate_subscription",
    "auto_activate",
    "verify_and_activate",
}


def _public_protocol_methods(protocol: type) -> set[str]:
    return {name for name, value in inspect.getmembers(protocol) if callable(value) and not name.startswith("_")}


def test_persistence_errors_have_stable_hierarchy() -> None:
    assert issubclass(
        errors.AdminMarketplaceNotFoundError,
        errors.AdminMarketplacePersistenceError,
    )
    assert issubclass(
        errors.AdminMarketplaceConflictError,
        errors.AdminMarketplacePersistenceError,
    )
    assert issubclass(
        errors.AdminMarketplaceConcurrencyError,
        errors.AdminMarketplaceConflictError,
    )
    assert issubclass(
        errors.AdminMarketplaceDuplicateReferenceError,
        errors.AdminMarketplaceConflictError,
    )
    assert issubclass(
        errors.AdminMarketplaceImmutableRecordError,
        errors.AdminMarketplaceConflictError,
    )


def test_commercial_audit_repository_is_append_only() -> None:
    methods = _public_protocol_methods(CommercialAuditRepository)

    assert {"append", "get_by_id", "list_by_resource"} <= methods

    assert methods.isdisjoint(
        {
            "delete",
            "save",
            "save_or_update",
            "update",
            "upsert",
        }
    )


def test_unit_of_work_owns_transaction_boundary() -> None:
    methods = _public_protocol_methods(AdminMarketplaceUnitOfWork)

    assert {"commit", "rollback"} <= methods


@pytest.mark.parametrize("repository_protocol", REPOSITORY_PROTOCOLS)
def test_repository_contracts_do_not_expose_transaction_methods(
    repository_protocol: type,
) -> None:
    methods = _public_protocol_methods(repository_protocol)

    assert methods.isdisjoint(TRANSACTION_METHODS)


@pytest.mark.parametrize("repository_protocol", REPOSITORY_PROTOCOLS)
def test_repository_contracts_have_no_automatic_activation_api(
    repository_protocol: type,
) -> None:
    methods = _public_protocol_methods(repository_protocol)

    assert methods.isdisjoint(AUTOMATIC_ACTIVATION_METHODS)


def test_repository_contracts_do_not_expose_generic_mutation_api() -> None:
    prohibited = {
        "delete",
        "patch",
        "save",
        "save_or_update",
        "update",
        "upsert",
    }

    for repository_protocol in REPOSITORY_PROTOCOLS:
        methods = _public_protocol_methods(repository_protocol)
        assert methods.isdisjoint(prohibited)
