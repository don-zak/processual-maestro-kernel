from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_kernel.notifications import discord as discord_mod
from processual_kernel.notifications import rate_limit as rate_limit_mod
from processual_kernel.notifications import templates as templates_mod
from processual_kernel.notifications.types import AlertPayload, AlertSeverity, AlertType


def test_rate_limiter_uses_environment_and_enforces_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_RATE_LIMIT_SECONDS", "5")
    clock = iter([10.0, 12.0, 15.0])
    monkeypatch.setattr(rate_limit_mod.time, "time", lambda: next(clock))

    limiter = rate_limit_mod.RateLimiter()

    assert limiter._interval == 5.0
    assert limiter.allow() is True
    assert limiter.allow() is False
    assert limiter.allow() is True


def test_rate_limiter_reset_allows_next_send(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISCORD_RATE_LIMIT_SECONDS", raising=False)
    clock = iter([100.0, 101.0, 200.0])
    monkeypatch.setattr(rate_limit_mod.time, "time", lambda: next(clock))

    limiter = rate_limit_mod.RateLimiter()
    assert limiter._interval == 30.0
    assert limiter.allow() is True
    assert limiter.allow() is False

    limiter.reset()
    assert limiter._last_send == 0.0
    assert limiter.allow() is True


def test_discord_notifier_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook")
    monkeypatch.setenv("DISCORD_MIN_SEVERITY", "critical")
    monkeypatch.setenv("DISCORD_ALERTS_ENABLED", "FALSE")

    notifier = discord_mod.DiscordNotifier()

    assert notifier.webhook_url == "https://example.invalid/webhook"
    assert notifier.min_severity is AlertSeverity.CRITICAL
    assert notifier.enabled is False


def test_discord_notifier_explicit_webhook_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "env-webhook")
    monkeypatch.setenv("DISCORD_MIN_SEVERITY", "warning")
    monkeypatch.setenv("DISCORD_ALERTS_ENABLED", "true")

    notifier = discord_mod.DiscordNotifier(webhook_url="explicit-webhook")

    assert notifier.webhook_url == "explicit-webhook"
    assert notifier.min_severity is AlertSeverity.WARNING
    assert notifier.enabled is True


@pytest.mark.parametrize(
    ("minimum", "severity", "expected"),
    [
        (AlertSeverity.INFO, AlertSeverity.INFO, True),
        (AlertSeverity.INFO, AlertSeverity.WARNING, True),
        (AlertSeverity.WARNING, AlertSeverity.INFO, False),
        (AlertSeverity.WARNING, AlertSeverity.WARNING, True),
        (AlertSeverity.WARNING, AlertSeverity.CRITICAL, True),
        (AlertSeverity.CRITICAL, AlertSeverity.WARNING, False),
        (AlertSeverity.CRITICAL, AlertSeverity.CRITICAL, True),
    ],
)
def test_severity_threshold_order(minimum: AlertSeverity, severity: AlertSeverity, expected: bool) -> None:
    notifier = discord_mod.DiscordNotifier.__new__(discord_mod.DiscordNotifier)
    notifier.min_severity = minimum

    assert notifier._severity_met(severity) is expected


def _payload(severity: AlertSeverity = AlertSeverity.WARNING) -> AlertPayload:
    return AlertPayload(
        alert_type=AlertType.WORKFLOW_FAILURE,
        severity=severity,
        title="Workflow Alert",
        description="Workflow wf-1 failed",
        fields={"Workflow": "wf-1", "Status": "failed"},
        workflow_id="wf-1",
    )


def test_send_blocks_when_disabled_or_missing_webhook() -> None:
    notifier = discord_mod.DiscordNotifier.__new__(discord_mod.DiscordNotifier)
    notifier.enabled = False
    notifier.webhook_url = "webhook"
    notifier.min_severity = AlertSeverity.WARNING
    notifier._rate_limiter = Mock()

    assert notifier.send(_payload()) == {
        "sent": False,
        "reason": "notifier disabled or no webhook URL",
    }

    notifier.enabled = True
    notifier.webhook_url = None
    assert notifier.send(_payload()) == {
        "sent": False,
        "reason": "notifier disabled or no webhook URL",
    }


def test_send_blocks_below_severity_and_rate_limit() -> None:
    notifier = discord_mod.DiscordNotifier.__new__(discord_mod.DiscordNotifier)
    notifier.enabled = True
    notifier.webhook_url = "webhook"
    notifier.min_severity = AlertSeverity.CRITICAL
    notifier._rate_limiter = Mock()

    assert notifier.send(_payload(AlertSeverity.WARNING)) == {
        "sent": False,
        "reason": "severity warning below minimum critical",
    }
    notifier._rate_limiter.allow.assert_not_called()

    notifier.min_severity = AlertSeverity.WARNING
    notifier._rate_limiter.allow.return_value = False
    assert notifier.send(_payload()) == {"sent": False, "reason": "rate limited"}


def test_send_posts_expected_discord_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    response = Mock(status_code=204)
    response.raise_for_status = Mock()
    post = Mock(return_value=response)
    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(post=post))

    notifier = discord_mod.DiscordNotifier.__new__(discord_mod.DiscordNotifier)
    notifier.enabled = True
    notifier.webhook_url = "https://example.invalid/webhook"
    notifier.min_severity = AlertSeverity.INFO
    notifier._rate_limiter = Mock()
    notifier._rate_limiter.allow.return_value = True

    result = notifier.send(_payload(AlertSeverity.CRITICAL))

    assert result == {"sent": True, "status_code": 204}
    response.raise_for_status.assert_called_once_with()
    post.assert_called_once_with(
        "https://example.invalid/webhook",
        json={
            "embeds": [
                {
                    "title": "Workflow Alert",
                    "description": "Workflow wf-1 failed",
                    "color": 15548997,
                    "fields": [
                        {"name": "Workflow", "value": "wf-1", "inline": True},
                        {"name": "Status", "value": "failed", "inline": True},
                    ],
                    "footer": {"text": "Processual Maestro | WORKFLOW_FAILURE"},
                }
            ]
        },
        timeout=10.0,
    )


def test_send_returns_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    post = Mock(side_effect=RuntimeError("discord unavailable"))
    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(post=post))

    notifier = discord_mod.DiscordNotifier.__new__(discord_mod.DiscordNotifier)
    notifier.enabled = True
    notifier.webhook_url = "webhook"
    notifier.min_severity = AlertSeverity.WARNING
    notifier._rate_limiter = Mock()
    notifier._rate_limiter.allow.return_value = True

    assert notifier.send(_payload()) == {"sent": False, "reason": "discord unavailable"}


def test_send_fate_alert_threshold_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    notifier = Mock()
    notifier.send.return_value = {"sent": True}
    monkeypatch.setattr(discord_mod, "_make_notifier", Mock(return_value=notifier))

    assert discord_mod.send_fate_alert("extinct", 0.10, 0.72, "wf-ext") == {"sent": True}
    extinction_payload = notifier.send.call_args.args[0]
    assert extinction_payload.alert_type is AlertType.FATE_EXTINCTION_RISK
    assert extinction_payload.severity is AlertSeverity.CRITICAL
    assert extinction_payload.fields == {"Extinction": "0.72", "Rank": "extinct"}
    assert extinction_payload.workflow_id == "wf-ext"

    notifier.reset_mock()
    notifier.send.return_value = {"sent": True}
    assert discord_mod.send_fate_alert("distorted", 0.62, 0.20) == {"sent": True}
    distortion_payload = notifier.send.call_args.args[0]
    assert distortion_payload.alert_type is AlertType.FATE_DISTORTION_SPIKE
    assert distortion_payload.severity is AlertSeverity.WARNING
    assert distortion_payload.description == "Workflow unknown shows high distortion"
    assert distortion_payload.fields == {"Distortion": "0.62", "Rank": "distorted"}

    notifier.reset_mock()
    assert discord_mod.send_fate_alert("stable", 0.61, 0.71, "wf-safe") == {
        "sent": False,
        "reason": "no alert threshold triggered",
    }
    notifier.send.assert_not_called()


def test_workflow_and_security_helpers_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    notifier = Mock()
    notifier.send.side_effect = [{"sent": True, "kind": "workflow"}, {"sent": True, "kind": "security"}]
    monkeypatch.setattr(discord_mod, "_make_notifier", Mock(return_value=notifier))

    workflow_result = discord_mod.send_workflow_alert("wf-9", "paused", AlertSeverity.INFO)
    security_result = discord_mod.send_security_alert(
        "signature mismatch",
        AlertSeverity.CRITICAL,
        {"Key": "k-7"},
    )

    assert workflow_result == {"sent": True, "kind": "workflow"}
    workflow_payload = notifier.send.call_args_list[0].args[0]
    assert workflow_payload.alert_type is AlertType.WORKFLOW_FAILURE
    assert workflow_payload.severity is AlertSeverity.INFO
    assert workflow_payload.fields == {"Workflow": "wf-9", "Status": "paused"}

    assert security_result == {"sent": True, "kind": "security"}
    security_payload = notifier.send.call_args_list[1].args[0]
    assert security_payload.alert_type is AlertType.SECURITY_CRYPTO_FAILURE
    assert security_payload.title == "Security Alert"
    assert security_payload.fields == {"Key": "k-7"}


def test_security_helper_defaults_to_empty_details(monkeypatch: pytest.MonkeyPatch) -> None:
    notifier = Mock()
    notifier.send.return_value = {"sent": True}
    monkeypatch.setattr(discord_mod, "_make_notifier", Mock(return_value=notifier))

    assert discord_mod.send_security_alert("crypto failure") == {"sent": True}
    payload = notifier.send.call_args.args[0]
    assert payload.severity is AlertSeverity.CRITICAL
    assert payload.fields == {}


def test_fate_alert_embed_and_rank_colors() -> None:
    embed = templates_mod.fate_alert_embed("Distorted", 0.8, 0.63, 0.1, "review")

    assert embed == {
        "title": "CGT Fate: Distorted",
        "color": 15158332,
        "fields": [
            {"name": "Stability", "value": "0.80", "inline": True},
            {"name": "Distortion", "value": "0.63", "inline": True},
            {"name": "Extinction", "value": "0.10", "inline": True},
            {"name": "Recommendation", "value": "review", "inline": False},
        ],
    }
    assert templates_mod._color_for_rank("unknown") == 5814783


def test_other_notification_templates() -> None:
    workflow = templates_mod.workflow_alert_embed("wf-1", "running", "controlled")
    assert workflow["title"] == "Workflow wf-1"
    assert workflow["color"] == 5814783
    assert workflow["fields"][1] == {"name": "Runtime Mode", "value": "controlled", "inline": True}

    security = templates_mod.security_alert_embed("CRYPTO_FAILURE", "bad tag")
    assert security == {
        "title": "Security: CRYPTO_FAILURE",
        "color": 15548997,
        "fields": [{"name": "Description", "value": "bad tag", "inline": False}],
    }

    success = templates_mod.deployment_alert_embed("2.0.0", "prod", "success")
    failure = templates_mod.deployment_alert_embed("2.0.0", "prod", "failed")
    assert success["color"] == 5814783
    assert failure["color"] == 15158332
    assert failure["fields"][-1] == {"name": "Status", "value": "failed", "inline": True}
