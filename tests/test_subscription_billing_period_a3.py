from __future__ import annotations

from datetime import UTC, datetime

from processual_api.admin_marketplace.subscription_billing_period import (
    next_anchored_month_boundary,
    quota_period_end,
    subscription_period_end,
)


def test_monthly_period_runs_from_activation_timestamp_to_same_timestamp_next_month() -> None:
    activated_at = datetime(2026, 8, 17, 14, 30, 45, tzinfo=UTC)

    assert subscription_period_end(
        starts_at=activated_at,
        billing_period="monthly",
    ) == datetime(2026, 9, 17, 14, 30, 45, tzinfo=UTC)
    assert quota_period_end(
        starts_at=activated_at,
        period_days=30,
    ) == datetime(2026, 9, 17, 14, 30, 45, tzinfo=UTC)


def test_monthly_period_is_not_aligned_to_first_day_of_calendar_month() -> None:
    activated_at = datetime(2026, 8, 17, 14, 30, tzinfo=UTC)
    expires_at = subscription_period_end(
        starts_at=activated_at,
        billing_period="monthly",
    )

    assert expires_at.day == 17
    assert expires_at.hour == 14
    assert expires_at.minute == 30


def test_original_activation_day_returns_after_short_month() -> None:
    activated_at = datetime(2026, 1, 31, 14, 30, tzinfo=UTC)
    february_boundary = quota_period_end(starts_at=activated_at, period_days=30)
    march_boundary = next_anchored_month_boundary(
        starts_at=february_boundary,
        anchor_day=activated_at.day,
    )

    assert february_boundary == datetime(2026, 2, 28, 14, 30, tzinfo=UTC)
    assert march_boundary == datetime(2026, 3, 31, 14, 30, tzinfo=UTC)
