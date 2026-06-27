from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .rate_limit import RateLimiter
from .types import AlertPayload, AlertSeverity, AlertType


@dataclass
class DiscordNotifier:
    webhook_url: str | None = None
    min_severity: AlertSeverity = AlertSeverity.WARNING
    enabled: bool = True
    _rate_limiter: RateLimiter = RateLimiter()

    def __post_init__(self) -> None:
        if self.webhook_url is None:
            self.webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
        min_sev = os.environ.get("DISCORD_MIN_SEVERITY", "warning")
        self.min_severity = AlertSeverity(min_sev)
        enabled_str = os.environ.get("DISCORD_ALERTS_ENABLED", "true")
        self.enabled = enabled_str.lower() == "true"

    def _severity_met(self, severity: AlertSeverity) -> bool:
        order = {AlertSeverity.INFO: 0, AlertSeverity.WARNING: 1, AlertSeverity.CRITICAL: 2}
        return order.get(severity, 0) >= order.get(self.min_severity, 1)

    def send(self, payload: AlertPayload) -> dict[str, Any]:
        if not self.enabled or not self.webhook_url:
            return {"sent": False, "reason": "notifier disabled or no webhook URL"}
        if not self._severity_met(payload.severity):
            return {
                "sent": False,
                "reason": f"severity {payload.severity.value} below minimum {self.min_severity.value}",
            }
        if not self._rate_limiter.allow():
            return {"sent": False, "reason": "rate limited"}

        color_map = {
            AlertSeverity.INFO: 5814783,
            AlertSeverity.WARNING: 15158332,
            AlertSeverity.CRITICAL: 15548997,
        }
        fields = [{"name": k, "value": v, "inline": True} for k, v in payload.fields.items()]
        embed = {
            "title": payload.title,
            "description": payload.description,
            "color": color_map.get(payload.severity, 5814783),
            "fields": fields,
            "footer": {"text": f"Processual Maestro | {payload.alert_type.value}"},
        }

        try:
            import httpx

            resp = httpx.post(
                self.webhook_url,
                json={"embeds": [embed]},
                timeout=10.0,
            )
            resp.raise_for_status()
            return {"sent": True, "status_code": resp.status_code}
        except Exception as exc:
            return {"sent": False, "reason": str(exc)}


def _make_notifier() -> DiscordNotifier:
    return DiscordNotifier()


def send_fate_alert(
    rank: str,
    distortion: float,
    extinction: float,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    notifier = _make_notifier()
    if extinction >= 0.72:
        payload = AlertPayload(
            alert_type=AlertType.FATE_EXTINCTION_RISK,
            severity=AlertSeverity.CRITICAL,
            title="CGT Fate Alert: Extinction Risk",
            description=f"Workflow {workflow_id or 'unknown'} has high extinction risk",
            fields={"Extinction": f"{extinction:.2f}", "Rank": rank},
            workflow_id=workflow_id,
        )
    elif distortion >= 0.62:
        payload = AlertPayload(
            alert_type=AlertType.FATE_DISTORTION_SPIKE,
            severity=AlertSeverity.WARNING,
            title="CGT Fate Alert: Distortion Spike",
            description=f"Workflow {workflow_id or 'unknown'} shows high distortion",
            fields={"Distortion": f"{distortion:.2f}", "Rank": rank},
            workflow_id=workflow_id,
        )
    else:
        return {"sent": False, "reason": "no alert threshold triggered"}
    return notifier.send(payload)


def send_workflow_alert(
    workflow_id: str,
    status: str,
    severity: AlertSeverity = AlertSeverity.WARNING,
) -> dict[str, Any]:
    notifier = _make_notifier()
    payload = AlertPayload(
        alert_type=AlertType.WORKFLOW_FAILURE,
        severity=severity,
        title="Workflow Alert",
        description=f"Workflow {workflow_id} status: {status}",
        fields={"Workflow": workflow_id, "Status": status},
        workflow_id=workflow_id,
    )
    return notifier.send(payload)


def send_security_alert(
    message: str,
    severity: AlertSeverity = AlertSeverity.CRITICAL,
    details: dict[str, str] | None = None,
) -> dict[str, Any]:
    notifier = _make_notifier()
    payload = AlertPayload(
        alert_type=AlertType.SECURITY_CRYPTO_FAILURE,
        severity=severity,
        title="Security Alert",
        description=message,
        fields=details or {},
    )
    return notifier.send(payload)
