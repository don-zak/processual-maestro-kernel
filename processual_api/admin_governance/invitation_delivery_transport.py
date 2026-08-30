from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

from processual_api.admin_governance.invitation_delivery_authority import (
    AdministratorInvitationDeliveryAuthority,
)
from processual_api.auth.delivery_provider import DeliveryProvider, validate_https_endpoint


class AdministratorInvitationDeliveryProvider(Protocol):
    async def send_verification_email(
        self,
        *,
        template: str,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AdministratorInvitationDeliveryReceipt:
    invitation_id: uuid.UUID
    recipient_email: str
    acceptance_url: str


class AdministratorInvitationDeliveryTransport:
    def __init__(
        self,
        *,
        authority: AdministratorInvitationDeliveryAuthority,
        provider: DeliveryProvider,
        public_base_url: str,
    ) -> None:
        self._authority = authority
        self._provider = provider
        self._public_base_url = validate_https_endpoint(
            public_base_url,
            label="Administrator invitation public base URL",
        )

    def acceptance_url(
        self,
        *,
        invitation_id: uuid.UUID,
        invitation_token: str,
    ) -> str:
        query = urlencode(
            {
                "invitation_id": str(invitation_id),
                "token": invitation_token,
            }
        )
        return f"{self._public_base_url}/admin/invitations/accept?{query}"

    async def deliver(
        self,
        *,
        invitation_id: uuid.UUID,
        invitation_token: str,
    ) -> AdministratorInvitationDeliveryReceipt:
        grant = await self._authority.authorize(
            invitation_id=invitation_id,
            invitation_token=invitation_token,
        )
        acceptance_url = self.acceptance_url(
            invitation_id=invitation_id,
            invitation_token=invitation_token,
        )
        await self._provider.send_verification_email(
            template="admin_governance_invitation",
            recipient=grant.email_normalized,
            verification_url=acceptance_url,
            idempotency_key=f"pmk-admin-invitation-v1:{invitation_id}",
        )
        return AdministratorInvitationDeliveryReceipt(
            invitation_id=invitation_id,
            recipient_email=grant.email_normalized,
            acceptance_url=acceptance_url,
        )


__all__ = [
    "AdministratorInvitationDeliveryReceipt",
    "AdministratorInvitationDeliveryTransport",
]
