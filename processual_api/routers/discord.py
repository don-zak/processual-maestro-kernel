"""Discord notification routes — webhook testing and status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..auth.platform_admin_authority import require_active_platform_admin
from ..auth.security import get_current_user
from ..services.discord_service import DiscordService

router = APIRouter(prefix="/discord", tags=["discord"])


class DiscordWebhookTestRequest(BaseModel):
    message: str = "CGT Fate Alert -- test notification from Processual Maestro Kernel API"


class DiscordWebhookTestResponse(BaseModel):
    success: bool
    message: str


async def _require_discord_test_send_authority(
    current_user: dict,
    request: Request,
) -> None:
    await require_active_platform_admin(current_user, request)


@router.post("/webhook/test", response_model=DiscordWebhookTestResponse)
async def test_discord_webhook(
    req: DiscordWebhookTestRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_discord_test_send_authority(current_user, request)
    svc = DiscordService()
    sent = await svc.send_client(req.message)
    if not sent and not svc.has_client_webhook:
        return DiscordWebhookTestResponse(success=False, message="DISCORD_WEBHOOK_URL not configured")
    return DiscordWebhookTestResponse(
        success=True,
        message="Client channel notification sent" if sent else "Rate limited",
    )


@router.post("/webhook/test-admin", response_model=DiscordWebhookTestResponse)
async def test_discord_admin_webhook(
    req: DiscordWebhookTestRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    await _require_discord_test_send_authority(current_user, request)
    svc = DiscordService()
    sent = await svc.send_admin(req.message)
    if not sent and not svc.has_admin_webhook:
        return DiscordWebhookTestResponse(success=False, message="DISCORD_ADMIN_WEBHOOK_URL not configured")
    return DiscordWebhookTestResponse(
        success=True,
        message="Admin channel notification sent" if sent else "Rate limited",
    )
