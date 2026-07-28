"""Strict public contracts for customer billing profiles."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _StrictBillingModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class BillingProfileUpsertRequest(_StrictBillingModel):
    country_code: str = Field(min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=160)
    city: str | None = Field(default=None, max_length=160)
    postal_code: str | None = Field(default=None, max_length=32)
    address_line_1: str | None = Field(default=None, max_length=300)
    address_line_2: str | None = Field(default=None, max_length=300)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must be a two-letter ISO code.")
        return normalized

    @field_validator(
        "region",
        "city",
        "postal_code",
        "address_line_1",
        "address_line_2",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class BillingProfileResponse(_StrictBillingModel):
    id: UUID
    user_id: UUID
    organization_id: UUID | None
    country_code: str
    region: str | None
    city: str | None
    postal_code: str | None
    address_line_1: str | None
    address_line_2: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )
