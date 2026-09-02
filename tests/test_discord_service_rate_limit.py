from __future__ import annotations

import asyncio

from processual_api.services.discord_service import DiscordService


def _reset_rate_limits(monkeypatch) -> None:
    monkeypatch.setattr(DiscordService, "_last_send_by_target", {})


def test_rate_limit_is_shared_across_request_scoped_instances(monkeypatch) -> None:
    _reset_rate_limits(monkeypatch)
    monkeypatch.setenv("DISCORD_RATE_LIMIT_SECONDS", "30")
    sent_payloads: list[tuple[str, str]] = []

    async def fake_post(self, webhook_url: str, payload: dict) -> bool:
        sent_payloads.append((webhook_url, payload["content"]))
        return True

    monkeypatch.setattr(DiscordService, "_post", fake_post)

    first = DiscordService(client_webhook="https://discord.example/shared-secret")
    second = DiscordService(client_webhook="https://discord.example/shared-secret")

    assert asyncio.run(first.send_client("first")) is True
    assert asyncio.run(second.send_client("second")) is False
    assert sent_payloads == [("https://discord.example/shared-secret", "first")]


def test_rate_limit_does_not_cross_webhook_targets(monkeypatch) -> None:
    _reset_rate_limits(monkeypatch)
    monkeypatch.setenv("DISCORD_RATE_LIMIT_SECONDS", "30")
    sent_payloads: list[str] = []

    async def fake_post(self, webhook_url: str, payload: dict) -> bool:
        sent_payloads.append(webhook_url)
        return True

    monkeypatch.setattr(DiscordService, "_post", fake_post)

    first = DiscordService(client_webhook="https://discord.example/client-a")
    second = DiscordService(client_webhook="https://discord.example/client-b")

    assert asyncio.run(first.send_client("a")) is True
    assert asyncio.run(second.send_client("b")) is True
    assert sent_payloads == [
        "https://discord.example/client-a",
        "https://discord.example/client-b",
    ]


def test_rate_limit_keeps_admin_and_client_channels_independent(monkeypatch) -> None:
    _reset_rate_limits(monkeypatch)
    monkeypatch.setenv("DISCORD_RATE_LIMIT_SECONDS", "30")
    monkeypatch.setenv("DISCORD_ADMIN_WEBHOOK_URL", "https://discord.example/shared")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/shared")
    sent_payloads: list[str] = []

    async def fake_post(self, webhook_url: str, payload: dict) -> bool:
        sent_payloads.append(payload["content"])
        return True

    monkeypatch.setattr(DiscordService, "_post", fake_post)
    service = DiscordService()

    assert asyncio.run(service.send_admin("admin")) is True
    assert asyncio.run(service.send_client("client")) is True
    assert sent_payloads == ["admin", "client"]


def test_rate_limit_key_does_not_store_raw_webhook_secret(monkeypatch) -> None:
    _reset_rate_limits(monkeypatch)
    monkeypatch.setenv("DISCORD_RATE_LIMIT_SECONDS", "30")
    raw_webhook = "https://discord.example/super-secret-token"

    async def fake_post(self, webhook_url: str, payload: dict) -> bool:
        return True

    monkeypatch.setattr(DiscordService, "_post", fake_post)
    service = DiscordService(client_webhook=raw_webhook)

    assert asyncio.run(service.send_client("first")) is True
    keys = list(DiscordService._last_send_by_target)
    assert keys
    assert raw_webhook not in str(keys)
    assert keys[0][0] == "client"
    assert len(keys[0][1]) == 64
