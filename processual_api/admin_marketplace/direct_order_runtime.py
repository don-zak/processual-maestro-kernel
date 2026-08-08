from __future__ import annotations

from datetime import UTC, datetime

from processual_api.admin_marketplace.contract_service import (
    DirectContractCompletionService,
)
from processual_api.admin_marketplace.direct_order_service import (
    TunisiaDirectOrderService,
)
from processual_api.admin_marketplace.payment_evidence_service import (
    CustomerPaymentEvidenceService,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.db.session import get_session_factory


class DirectOrderRuntimeUnavailableError(RuntimeError):
    """Raised when the direct-order persistence authority is unavailable."""


def build_direct_order_service() -> TunisiaDirectOrderService:
    try:
        session_factory = get_session_factory()

        def unit_of_work_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
            return SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)

        return TunisiaDirectOrderService(
            unit_of_work_factory=unit_of_work_factory,
            clock=lambda: datetime.now(UTC),
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise DirectOrderRuntimeUnavailableError("Direct-order runtime is unavailable.") from exc


def build_contract_completion_service() -> DirectContractCompletionService:
    try:
        session_factory = get_session_factory()

        def unit_of_work_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
            return SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)

        return DirectContractCompletionService(
            unit_of_work_factory=unit_of_work_factory,
            clock=lambda: datetime.now(UTC),
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise DirectOrderRuntimeUnavailableError("Contract-completion runtime is unavailable.") from exc


def build_customer_payment_evidence_service() -> CustomerPaymentEvidenceService:
    try:
        session_factory = get_session_factory()

        def unit_of_work_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
            return SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)

        return CustomerPaymentEvidenceService(
            unit_of_work_factory=unit_of_work_factory,
            clock=lambda: datetime.now(UTC),
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise DirectOrderRuntimeUnavailableError("Payment-evidence runtime is unavailable.") from exc


__all__ = [
    "DirectOrderRuntimeUnavailableError",
    "build_contract_completion_service",
    "build_customer_payment_evidence_service",
    "build_direct_order_service",
]
