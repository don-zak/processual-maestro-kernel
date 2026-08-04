from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from processual_api.admin_marketplace.eligibility_service import (
    AdminMarketplaceEligibilityService,
)
from processual_api.admin_marketplace.identity_authority import (
    AdminMarketplaceIdentityAuthorityResolver,
)
from processual_api.admin_marketplace.payment_destination_crypto import (
    PaymentDestinationCipher,
)
from processual_api.admin_marketplace.payment_destination_service import (
    PaymentDestinationAdministrationService,
)
from processual_api.admin_marketplace.persistence.unit_of_work import (
    SqlAlchemyAdminMarketplaceUnitOfWork,
)
from processual_api.db.session import get_session_factory
from processual_api.settings import APISettings, settings


class AdminMarketplaceRuntimeUnavailableError(RuntimeError):
    """Admin Marketplace read authority is unavailable."""


@dataclass(frozen=True, slots=True)
class AdminMarketplaceRuntime:
    authority_resolver: AdminMarketplaceIdentityAuthorityResolver
    eligibility_service: AdminMarketplaceEligibilityService
    payment_destination_service: PaymentDestinationAdministrationService | None


def _payment_destination_keys(raw_json: str | None) -> dict[str, bytes]:
    if raw_json is None:
        raise AdminMarketplaceRuntimeUnavailableError(
            "Admin Marketplace payment destination key authority is unavailable."
        )
    try:
        payload = json.loads(raw_json)
        if not isinstance(payload, dict) or not payload:
            raise ValueError
        keys = {
            str(version): base64.b64decode(encoded, validate=True)
            for version, encoded in payload.items()
            if isinstance(version, str) and isinstance(encoded, str)
        }
    except (
        ValueError,
        TypeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise AdminMarketplaceRuntimeUnavailableError(
            "Admin Marketplace payment destination key authority is invalid."
        ) from exc
    if len(keys) != len(payload):
        raise AdminMarketplaceRuntimeUnavailableError(
            "Admin Marketplace payment destination key authority is invalid."
        )
    return keys


async def build_admin_marketplace_runtime(
    config: APISettings = settings,
) -> AdminMarketplaceRuntime:
    try:
        session_factory = get_session_factory()
        mfa_step_up_max_age = timedelta(
            seconds=config.auth_mfa_step_up_seconds,
        )

        def unit_of_work_factory() -> SqlAlchemyAdminMarketplaceUnitOfWork:
            return SqlAlchemyAdminMarketplaceUnitOfWork(session_factory)

        authority_resolver = AdminMarketplaceIdentityAuthorityResolver(
            session_factory=session_factory,
            mfa_step_up_max_age=mfa_step_up_max_age,
        )
        eligibility_service = AdminMarketplaceEligibilityService(
            unit_of_work_factory=unit_of_work_factory,
        )
    except (RuntimeError, TypeError, ValueError) as exc:
        raise AdminMarketplaceRuntimeUnavailableError(
            "Admin Marketplace runtime authority is unavailable."
        ) from exc

    payment_destination_service = None
    try:
        payment_destination_service = PaymentDestinationAdministrationService(
            unit_of_work_factory=unit_of_work_factory,
            cipher=PaymentDestinationCipher(
                current_key_version=(
                    config.admin_marketplace_payment_destination_current_key_version
                    or ""
                ),
                keys=_payment_destination_keys(
                    config.admin_marketplace_payment_destination_key_ring_json
                ),
            ),
            clock=lambda: datetime.now(UTC),
        )
    except (AdminMarketplaceRuntimeUnavailableError, TypeError, ValueError):
        # Eligibility reads remain available; payment administration fails
        # closed at its dedicated dependency boundary.
        payment_destination_service = None

    return AdminMarketplaceRuntime(
        authority_resolver=authority_resolver,
        eligibility_service=eligibility_service,
        payment_destination_service=payment_destination_service,
    )


__all__ = [
    "AdminMarketplaceRuntime",
    "AdminMarketplaceRuntimeUnavailableError",
    "_payment_destination_keys",
    "build_admin_marketplace_runtime",
]
