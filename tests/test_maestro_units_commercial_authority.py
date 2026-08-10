from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

import processual_api.services.quota_store as quota_store
from processual_api.billing.maestro_units import (
    LEGACY_CREDIT_ALIAS_RATIO,
    MAESTRO_UNIT_METRIC,
    credits_from_maestro_units,
    maestro_capability_for_endpoint,
    maestro_units_for_endpoint,
)
from processual_api.billing.plan_capability_matrix import plan_can_execute
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_SPECS,
    QUOTA_METRIC_CODE,
)
from processual_api.billing.usage_pricing import (
    BILLING_SCOPE,
    monthly_unit_allowance,
    pricing_decision,
)


def _api_key_user() -> dict[str, str]:
    return {
        "sub": "maestro-units-user",
        "user_id": "maestro-units-user",
        "client_id": "maestro-units-client",
        "role": "service",
        "auth_method": "api_key",
        "session_type": "service_integration",
        "api_key_id": "key_maestro_units",
        "api_key_prefix": "pmk_units",
    }


def _write_settings(tmp_path, *, plan: str, used: int, limit: int | None = None, period: str = "2026-08", manual: bool = False):
    key = {
        "id": "key_maestro_units",
        "prefix": "pmk_units",
        "status": "enabled",
        "quota_used": used,
        "quota_period": period,
        "quota_rejected_count": 0,
    }
    if manual:
        assert limit is not None
        key.update({
            "quota_policy": {"source": "manual", "quotas": {"evaluation": limit}},
            "quota_limit": limit,
            "quota_limit_override": limit,
        })
    path = tmp_path / "settings_maestro_units.json"
    path.write_text(json.dumps({"subscription": {"plan": plan}, "api_keys": [key]}), encoding="utf-8")
    return path


def test_maestro_units_are_the_single_quota_metric() -> None:
    assert QUOTA_METRIC_CODE == MAESTRO_UNIT_METRIC == "maestro_units"
    assert BILLING_SCOPE == MAESTRO_UNIT_METRIC
    assert LEGACY_CREDIT_ALIAS_RATIO == 1
    assert credits_from_maestro_units(17) == 17


@pytest.mark.parametrize(
    ("endpoint", "item_count", "expected"),
    [
        ("/health/live", None, 0),
        ("/cgt/analyze", None, 1),
        ("/cgt/govern", None, 1),
        ("/cgt/govern/compare", None, 2),
        ("/cgt/govern/report", None, 3),
        ("/cgt/govern/auto-repair", None, 5),
        ("/reports/fate", None, 2),
        ("/reports/generate-llm", None, 5),
        ("/cgt/govern/batch", 7, 7),
    ],
)
def test_pricing_and_metering_share_one_maestro_unit_contract(endpoint: str, item_count: int | None, expected: int) -> None:
    assert maestro_units_for_endpoint(endpoint, item_count=item_count) == expected
    assert pricing_decision(endpoint, item_count=item_count).units_charged == expected


def test_authoritative_plan_allowances_are_distinct_and_monotonic_by_commercial_tier() -> None:
    expected = {
        "academic": 5_000,
        "starter": 10_000,
        "enterprise_integration_starter": 50_000,
        "business": 100_000,
        "enterprise_pilot": 500_000,
        "enterprise_core": 1_500_000,
        "enterprise_scale": 3_000_000,
        "enterprise_strategic": 5_000_000,
    }
    assert {code: spec.monthly_unit_allowance for code, spec in PLAN_FULFILLMENT_SPECS.items()} == expected
    for plan, allowance in expected.items():
        assert monthly_unit_allowance(plan) == allowance


def test_plan_capabilities_do_not_leak_between_commercial_plans() -> None:
    assert plan_can_execute("starter", "maestro_execution") is True
    assert plan_can_execute("starter", "enterprise_governance") is False
    assert plan_can_execute("business", "enterprise_governance") is False

    assert plan_can_execute("enterprise_integration_starter", "enterprise_governance") is True
    assert plan_can_execute("enterprise_integration_starter", "advanced_integration") is True
    assert plan_can_execute("enterprise_integration_starter", "advanced_integration", require_production=True) is False

    assert plan_can_execute("enterprise_pilot", "enterprise_governance") is True
    assert plan_can_execute("enterprise_pilot", "advanced_integration") is False
    assert plan_can_execute("enterprise_core", "advanced_integration") is False
    assert plan_can_execute("enterprise_scale", "advanced_integration") is True
    assert plan_can_execute("enterprise_strategic", "advanced_integration") is True


def test_advanced_governance_unit_rules_require_enterprise_governance() -> None:
    assert maestro_capability_for_endpoint("/cgt/govern") == "maestro_execution"
    assert maestro_capability_for_endpoint("/cgt/govern/compare") == "enterprise_governance"
    assert maestro_capability_for_endpoint("/cgt/govern/report") == "enterprise_governance"
    assert maestro_capability_for_endpoint("/cgt/govern/auto-repair") == "enterprise_governance"


def test_quota_accepts_exact_limit_and_rejects_limit_plus_one(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "_now", lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC))
    path = _write_settings(tmp_path, plan="business", used=9, limit=10, period="2026-08", manual=True)

    result = quota_store.consume_quota(
        _api_key_user(), method="POST", endpoint="/cgt/govern", quota_scope="evaluation", amount=1
    )
    assert result["quota"]["used"] == 10
    assert result["quota"]["remaining"] == 0
    assert result["quota"]["metric"] == MAESTRO_UNIT_METRIC

    with pytest.raises(HTTPException) as exc:
        quota_store.consume_quota(
            _api_key_user(), method="POST", endpoint="/cgt/govern", quota_scope="evaluation", amount=1
        )
    assert exc.value.status_code == 429
    assert exc.value.detail["quota_metric"] == MAESTRO_UNIT_METRIC
    stored = json.loads(path.read_text(encoding="utf-8"))["api_keys"][0]
    assert stored["quota_used"] == 10


def test_quota_resets_when_monthly_maestro_unit_period_changes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "_now", lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC))
    path = _write_settings(tmp_path, plan="business", used=10, limit=10, period="2026-07", manual=True)

    result = quota_store.consume_quota(
        _api_key_user(), method="POST", endpoint="/cgt/govern", quota_scope="evaluation", amount=2
    )
    assert result["quota"]["period"] == "2026-08"
    assert result["quota"]["used"] == 2
    assert result["quota"]["remaining"] == 8

    stored = json.loads(path.read_text(encoding="utf-8"))["api_keys"][0]
    assert stored["quota_period"] == "2026-08"
    assert stored["quota_used"] == 2
    assert stored["quota_metric"] == MAESTRO_UNIT_METRIC


def test_business_plan_cannot_spend_units_on_enterprise_governance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "_now", lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC))
    _write_settings(tmp_path, plan="business", used=0, period="2026-08", manual=False)

    with pytest.raises(HTTPException) as exc:
        quota_store.consume_quota(
            _api_key_user(),
            method="POST",
            endpoint="/cgt/govern/auto-repair",
            quota_scope="evaluation",
            amount=5,
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "plan_capability_denied"
    assert exc.value.detail["capability_code"] == "enterprise_governance"


def test_enterprise_plan_can_spend_exact_maestro_units_on_governance(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(quota_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(quota_store, "_now", lambda: datetime(2026, 8, 10, 12, 0, tzinfo=UTC))
    _write_settings(tmp_path, plan="enterprise_pilot", used=0, period="2026-08", manual=False)

    result = quota_store.consume_quota(
        _api_key_user(),
        method="POST",
        endpoint="/cgt/govern/auto-repair",
        quota_scope="evaluation",
        amount=maestro_units_for_endpoint("/cgt/govern/auto-repair"),
    )
    assert result["quota"]["requested"] == 5
    assert result["quota"]["used"] == 5
    assert result["quota"]["limit"] == 500_000
    assert result["quota"]["metric"] == MAESTRO_UNIT_METRIC
