from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DeliveryOperationalMetricsResponseContract(
    BaseModel
):
    model_config = ConfigDict(extra="forbid")

    pending_count: int = Field(ge=0)
    retry_scheduled_count: int = Field(ge=0)
    leased_count: int = Field(ge=0)
    dead_letter_count: int = Field(ge=0)
    delivered_count: int = Field(ge=0)
    oldest_pending_age_seconds: int | None = Field(
        default=None,
        ge=0,
    )


class DeliveryRedriveAcceptedResponseContract(
    BaseModel
):
    model_config = ConfigDict(extra="forbid")

    status: str = "accepted"


__all__ = [
    "DeliveryOperationalMetricsResponseContract",
    "DeliveryRedriveAcceptedResponseContract",
]
