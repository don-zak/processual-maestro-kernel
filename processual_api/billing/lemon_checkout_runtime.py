from __future__ import annotations

from datetime import UTC, datetime

from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.billing.lemon_checkout_order_authority import (
    LemonCheckoutOrderAuthority,
)
from processual_api.db.session import get_session_factory


def build_lemon_checkout_order_authority() -> LemonCheckoutOrderAuthority:
    session_factory = get_session_factory()

    def unit_of_work_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
        return SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)

    return LemonCheckoutOrderAuthority(
        unit_of_work_factory=unit_of_work_factory,
        clock=lambda: datetime.now(UTC),
    )


__all__ = ["build_lemon_checkout_order_authority"]
