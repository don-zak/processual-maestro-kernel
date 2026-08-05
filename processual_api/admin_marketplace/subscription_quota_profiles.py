from __future__ import annotations

from dataclasses import dataclass

from processual_api.admin_marketplace.subscription_runtime import (
    SubscriptionRuntimeError,
)


@dataclass(frozen=True, slots=True)
class SubscriptionQuotaMetric:
    metric_code: str
    limit_units: int


@dataclass(frozen=True, slots=True)
class SubscriptionQuotaProfile:
    profile_ref: str
    period_days: int
    metrics: tuple[SubscriptionQuotaMetric, ...]


def validate_quota_profile(profile: SubscriptionQuotaProfile) -> SubscriptionQuotaProfile:
    profile_ref = profile.profile_ref.strip().lower()
    if not profile_ref or len(profile_ref) > 128:
        raise SubscriptionRuntimeError("quota profile reference is invalid.")
    if isinstance(profile.period_days, bool) or not isinstance(profile.period_days, int):
        raise SubscriptionRuntimeError("quota profile period must be an integer.")
    if profile.period_days < 1 or profile.period_days > 366:
        raise SubscriptionRuntimeError("quota profile period is outside allowed bounds.")
    if not profile.metrics:
        raise SubscriptionRuntimeError("quota profile must define at least one metric.")

    seen: set[str] = set()
    normalized: list[SubscriptionQuotaMetric] = []
    for metric in profile.metrics:
        metric_code = metric.metric_code.strip().lower()
        if not metric_code or len(metric_code) > 128:
            raise SubscriptionRuntimeError("quota metric code is invalid.")
        if metric_code in seen:
            raise SubscriptionRuntimeError("quota profile contains duplicate metrics.")
        if isinstance(metric.limit_units, bool) or not isinstance(metric.limit_units, int):
            raise SubscriptionRuntimeError("quota limit must be an integer.")
        if metric.limit_units < 0:
            raise SubscriptionRuntimeError("quota limit cannot be negative.")
        seen.add(metric_code)
        normalized.append(
            SubscriptionQuotaMetric(
                metric_code=metric_code,
                limit_units=metric.limit_units,
            )
        )

    return SubscriptionQuotaProfile(
        profile_ref=profile_ref,
        period_days=profile.period_days,
        metrics=tuple(normalized),
    )


def build_quota_profile_catalog(
    profiles: tuple[SubscriptionQuotaProfile, ...],
) -> dict[str, SubscriptionQuotaProfile]:
    catalog: dict[str, SubscriptionQuotaProfile] = {}
    for profile in profiles:
        normalized = validate_quota_profile(profile)
        if normalized.profile_ref in catalog:
            raise SubscriptionRuntimeError("duplicate quota profile reference.")
        catalog[normalized.profile_ref] = normalized
    return catalog
