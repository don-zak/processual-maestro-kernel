from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from processual_api.auth import platform_admin_authority


@pytest.mark.asyncio
async def test_persisted_platform_admin_is_accepted(monkeypatch) -> None:
    class Resolver:
        async def resolve_with_session(self, **kwargs):
            return SimpleNamespace(role="platform_admin")

    monkeypatch.setattr(
        platform_admin_authority,
        "AdminMarketplaceIdentityAuthorityResolver",
        Resolver,
    )
    identity = {"email": "owner@example.test", "role": "supervisor"}
    assert await platform_admin_authority.require_active_platform_admin(identity) is identity


@pytest.mark.asyncio
async def test_non_platform_admin_is_rejected_even_with_admin_claim(monkeypatch) -> None:
    class Resolver:
        async def resolve_with_session(self, **kwargs):
            return SimpleNamespace(role="supervisor")

    monkeypatch.setattr(
        platform_admin_authority,
        "AdminMarketplaceIdentityAuthorityResolver",
        Resolver,
    )
    identity = {"email": "claimed-admin@example.test", "role": "owner_admin"}
    with pytest.raises(HTTPException) as exc_info:
        await platform_admin_authority.require_active_platform_admin(identity)
    assert exc_info.value.status_code == 403
