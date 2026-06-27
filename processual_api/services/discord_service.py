from __future__ import annotations

import os
import time
from typing import Any


class DiscordService:
    """Two-channel Discord notification service.

    Channels:
      - admin:  high-level system events (applications, billing, monitoring)
                configured via DISCORD_ADMIN_WEBHOOK_URL (falls back to DISCORD_WEBHOOK_URL)
      - client: user-facing alerts (agent status, workflow events)
                configured per-user via settings or env DISCORD_WEBHOOK_URL
    """

    def __init__(self, client_webhook: str | None = None):
        self._admin_webhook = (
            os.environ.get("DISCORD_ADMIN_WEBHOOK_URL")
            or os.environ.get("DISCORD_WEBHOOK_URL", "")
        )
        self._client_webhook = client_webhook or os.environ.get("DISCORD_WEBHOOK_URL", "")
        self._last_send: dict[str, float] = {"admin": 0.0, "client": 0.0}
        self._min_interval = float(os.environ.get("DISCORD_RATE_LIMIT_SECONDS", "2"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _rate_limited(self, channel: str) -> bool:
        now = time.monotonic()
        last_send = self._last_send.get(channel, 0.0)
        if last_send > 0.0 and now - last_send < self._min_interval:
            return True
        self._last_send[channel] = now
        return False

    async def _post(self, webhook_url: str, payload: dict) -> bool:
        if not webhook_url:
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(webhook_url, json=payload)
                return resp.status_code in (200, 204)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Low-level send methods
    # ------------------------------------------------------------------

    async def send_raw(self, channel: str, message: str, embed: dict | None = None) -> bool:
        if self._rate_limited(channel):
            return False
        webhook = self._admin_webhook if channel == "admin" else self._client_webhook
        payload: dict[str, Any] = {"content": message}
        if embed:
            payload["embeds"] = [embed]
        return await self._post(webhook, payload)

    async def send_client(self, message: str, embed: dict | None = None) -> bool:
        return await self.send_raw("client", message, embed)

    async def send_admin(self, message: str, embed: dict | None = None) -> bool:
        return await self.send_raw("admin", message, embed)

    # ------------------------------------------------------------------
    # High-level typed notifiers
    # ------------------------------------------------------------------

    async def send_agent_alert(self, agent_id: str, agent_name: str, state: str, reason: str = "") -> bool:
        embed = {
            "title": f"Agent: {agent_name}",
            "color": _color_for_state(state),
            "fields": [
                {"name": "ID", "value": agent_id, "inline": True},
                {"name": "State", "value": state, "inline": True},
                {"name": "Reason", "value": reason or "\u2014", "inline": False},
            ],
        }
        return await self.send_client(f"**Agent Status:** {agent_name} \u2192 `{state}`", embed)

    async def send_application_alert(self, app: dict, action: str = "submitted", reviewer: str = "") -> bool:
        msg = f"**Application {action}** \u2014 {app.get('full_name', '?')} ({app.get('email', '?')})"
        embed: dict[str, Any] = {
            "title": f"Application {action.capitalize()}",
            "color": 5814783 if action in ("submitted", "approved") else 15158332,
            "fields": [
                {"name": "Name", "value": app.get("full_name", "?"), "inline": True},
                {"name": "Email", "value": app.get("email", "?"), "inline": True},
                {"name": "Plan", "value": app.get("preferred_plan", "?"), "inline": True},
                {"name": "Type", "value": app.get("applicant_type", "?"), "inline": True},
            ],
        }
        if action == "submitted":
            embed["fields"].append({"name": "Use Case", "value": str(app.get("use_case", "?"))[:200], "inline": False})
            embed["fields"].append({"name": "LinkedIn", "value": app.get("linkedin_url", "\u2014"), "inline": False})
        if reviewer:
            embed["fields"].append({"name": "Reviewer", "value": reviewer, "inline": True})
        return await self.send_admin(msg, embed)

    async def send_billing_alert(self, event: str, user_id: str, details: dict[str, str] | None = None) -> bool:
        embed: dict[str, Any] = {
            "title": f"Billing: {event.replace('_', ' ').title()}",
            "color": _color_for_billing(event),
            "fields": [{"name": "User", "value": user_id, "inline": True}],
        }
        if details:
            for k, v in details.items():
                embed["fields"].append({"name": k.replace("_", " ").title(), "value": str(v), "inline": True})
        return await self.send_admin(f"**Billing Event:** {event}", embed)

    async def send_system_alert(
        self, title: str, description: str, severity: str = "warning",
        fields: dict[str, str] | None = None,
    ) -> bool:
        color = {"info": 5814783, "warning": 15158332, "critical": 15548997}.get(severity, 15158332)
        embed: dict[str, Any] = {"title": title, "description": description, "color": color}
        if fields:
            embed["fields"] = [{"name": k, "value": v, "inline": True} for k, v in fields.items()]
        return await self.send_admin(f"**{severity.upper()}:** {title}", embed)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def has_client_webhook(self) -> bool:
        return bool(self._client_webhook)

    @property
    def has_admin_webhook(self) -> bool:
        return bool(self._admin_webhook)


def _color_for_state(state: str) -> int:
    colors = {
        "active": 5763719,
        "pending": 16753920,
        "frozen": 5814783,
        "escalated": 15158332,
        "rehabilitating": 16744272,
        "deactivated": 15548997,
    }
    return colors.get(state.lower(), 5814783)


def _color_for_billing(event: str) -> int:
    if "failed" in event or "cancelled" in event:
        return 15548997
    if "created" in event or "success" in event:
        return 5763719
    return 5814783
