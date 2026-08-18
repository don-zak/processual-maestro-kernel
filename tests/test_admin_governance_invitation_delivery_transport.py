from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from processual_api.admin_governance.invitation_delivery_authority import (
    AdministratorInvitationDeliveryDeniedError,
    AdministratorInvitationDeliveryGrant,
)
from processual_api.admin_governance.invitation_delivery_transport import (
    AdministratorInvitationDeliveryTransport,
)


@dataclass
class FakeAuthority:
    grant: AdministratorInvitationDeliveryGrant | None
    denied: bool = False

    async def authorize(self, *, invitation_id: uuid.UUID, invitation_token: str):
        del invitation_token
        if self.denied or self.grant is None or self.grant.invitation_id != invitation_id:
            raise AdministratorInvitationDeliveryDeniedError(
                "Administrator invitation delivery authority is invalid."
            )
        return self.grant


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def send_verification_email(
        self,
        *,
        template: str,
        recipient: str,
        verification_url: str,
        idempotency_key: str,
    ) -> None:
        self.calls.append(
            {
                "template": template,
                "recipient": recipient,
                "verification_url": verification_url,
                "idempotency_key": idempotency_key,
            }
        )


def _grant() -> AdministratorInvitationDeliveryGrant:
    return AdministratorInvitationDeliveryGrant(
        invitation_id=uuid.UUID("00000000-0000-0000-0000-000000000049"),
        email_normalized="admin@example.com",
        supervision_level="operations_supervisor",
        expires_at=datetime(2026, 8, 18, 12, 0, tzinfo=UTC),
    )


def test_transport_requires_https_public_base_url() -> None:
    with pytest.raises(ValueError, match="HTTPS URL"):
        AdministratorInvitationDeliveryTransport(
            authority=FakeAuthority(_grant()),
            provider=FakeProvider(),
            public_base_url="http://example.com",
        )


@pytest.mark.asyncio
async def test_deliver_builds_encoded_acceptance_url_and_sends_bounded_template() -> None:
    grant = _grant()
    provider = FakeProvider()
    transport = AdministratorInvitationDeliveryTransport(
        authority=FakeAuthority(grant),
        provider=provider,
        public_base_url="https://console.example.com/",
    )
    token = "invite secret+/?=&"

    receipt = await transport.deliver(
        invitation_id=grant.invitation_id,
        invitation_token=token,
    )

    assert receipt.invitation_id == grant.invitation_id
    assert receipt.recipient_email == "admin@example.com"
    parsed = urlsplit(receipt.acceptance_url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "console.example.com"
    assert parsed.path == "/admin/invitations/accept"
    query = parse_qs(parsed.query)
    assert query == {
        "invitation_id": [str(grant.invitation_id)],
        "token": [token],
    }
    assert provider.calls == [
        {
            "template": "admin_governance_invitation",
            "recipient": "admin@example.com",
            "verification_url": receipt.acceptance_url,
            "idempotency_key": f"pmk-admin-invitation-v1:{grant.invitation_id}",
        }
    ]


@pytest.mark.asyncio
async def test_deliver_does_not_call_provider_when_authority_is_denied() -> None:
    grant = _grant()
    provider = FakeProvider()
    transport = AdministratorInvitationDeliveryTransport(
        authority=FakeAuthority(grant, denied=True),
        provider=provider,
        public_base_url="https://console.example.com",
    )

    with pytest.raises(AdministratorInvitationDeliveryDeniedError):
        await transport.deliver(
            invitation_id=grant.invitation_id,
            invitation_token="wrong-token",
        )

    assert provider.calls == []
