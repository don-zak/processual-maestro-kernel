from __future__ import annotations

from pydantic import BaseModel


class GeneralSettings(BaseModel):
    language: str = "en"
    refresh_interval: int = 30
    timezone: str = "UTC"


class LLMProviderConfig(BaseModel):
    provider: str = "opencode"
    api_key: str = ""
    model: str = ""


class LLMProviderStatus(BaseModel):
    configured: bool = False
    provider: str = ""
    model: str = ""
    last_tested: str | None = None


class NotificationSettings(BaseModel):
    discord_webhook: str = ""
    alert_level: str = "warning"


class SubscriptionInfo(BaseModel):
    plan: str = "Starter"
    status: str = "active"
    stage: str = "active"  # active | grace | suspended | expired
    renews_at: str | None = None
    seats: int = 1
    max_seats: int = 1
    payment_failures: int = 0
    suspended_at: str | None = None

    @property
    def is_operational(self) -> bool:
        return self.stage == "active"


class SettingsResponse(BaseModel):
    general: GeneralSettings
    llm_provider: LLMProviderStatus
    notifications: NotificationSettings
    subscription: SubscriptionInfo


class TestConnectionResult(BaseModel):
    success: bool
    latency_ms: float | None = None
    error: str | None = None
