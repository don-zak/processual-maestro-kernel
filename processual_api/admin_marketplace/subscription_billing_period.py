from __future__ import annotations

import calendar
from datetime import datetime, timedelta


def add_calendar_months(value: datetime, months: int) -> datetime:
    if value.tzinfo is None:
        raise ValueError("billing period anchor must be timezone-aware.")
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise ValueError("months must be a positive integer.")

    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def subscription_period_end(*, starts_at: datetime, billing_period: str) -> datetime:
    normalized = billing_period.strip().lower()
    if normalized == "monthly":
        return add_calendar_months(starts_at, 1)
    if normalized == "annual":
        return add_calendar_months(starts_at, 12)
    raise ValueError("unsupported subscription billing period.")


def quota_period_end(*, starts_at: datetime, period_days: int) -> datetime:
    """Keep legacy custom periods, but make the canonical 30-day profile a true anchored month."""
    if isinstance(period_days, bool) or not isinstance(period_days, int) or period_days < 1:
        raise ValueError("quota period must be a positive integer.")
    if period_days == 30:
        return add_calendar_months(starts_at, 1)
    return starts_at + timedelta(days=period_days)


__all__ = [
    "add_calendar_months",
    "quota_period_end",
    "subscription_period_end",
]
