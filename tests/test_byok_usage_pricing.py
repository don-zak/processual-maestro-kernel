from processual_api.billing.usage_pricing import (
    BILLING_POLICY,
    BILLING_SCOPE,
    ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE,
    PROVIDER_COST_INCLUDED,
    allows_enterprise_integration,
    monthly_unit_allowance,
    pricing_decision,
)


def test_byok_pricing_policy_excludes_provider_costs():
    decision = pricing_decision("/cgt/govern")

    assert decision.billing_policy == "byok"
    assert decision.billing_scope == "maestro_usage_units"
    assert decision.provider_cost_included is False
    assert PROVIDER_COST_INCLUDED is False
    assert BILLING_POLICY == "byok"
    assert BILLING_SCOPE == "maestro_usage_units"


def test_operational_endpoints_do_not_consume_paid_units():
    assert pricing_decision("/health/live").units_charged == 0
    assert pricing_decision("/health/ready").units_charged == 0
    assert pricing_decision("/adapters/status").units_charged == 0
    assert pricing_decision("/settings/subscription").units_charged == 0


def test_governance_endpoint_consumes_one_maestro_unit():
    decision = pricing_decision("/cgt/govern")

    assert decision.endpoint == "/cgt/govern"
    assert decision.endpoint_class == "governance_evaluation"
    assert decision.units_charged == 1


def test_batch_governance_units_scale_by_item_count():
    decision = pricing_decision("/cgt/govern/batch", item_count=7)

    assert decision.endpoint_class == "batch_governance_evaluation"
    assert decision.units_charged == 7


def test_report_and_auto_repair_endpoints_have_higher_unit_costs():
    assert pricing_decision("/reports/fate").units_charged == 2
    assert pricing_decision("/reports/generate-llm").units_charged == 5
    assert pricing_decision("/cgt/govern/auto-repair").units_charged == 5


def test_enterprise_integration_plan_allows_50000_monthly_units():
    assert ENTERPRISE_INTEGRATION_UNIT_ALLOWANCE == 50_000
    assert monthly_unit_allowance("enterprise") == 50_000
    assert monthly_unit_allowance("enterprise_integration") == 50_000
    assert allows_enterprise_integration("enterprise")
    assert allows_enterprise_integration("enterprise_integration")


def test_non_enterprise_plans_do_not_allow_enterprise_integration():
    assert monthly_unit_allowance("pilot_starter") == 50
    assert monthly_unit_allowance("starter") == 50
    assert not allows_enterprise_integration("pilot_starter")
    assert not allows_enterprise_integration("starter")


def test_pricing_decision_exports_usage_ledger_fields():
    record = pricing_decision("/cgt/govern").to_usage_record()

    assert record["endpoint"] == "/cgt/govern"
    assert record["endpoint_class"] == "governance_evaluation"
    assert record["units_charged"] == 1
    assert record["pricing_version"] == "2026-07-byok-v1"
    assert record["billing_policy"] == "byok"
    assert record["billing_scope"] == "maestro_usage_units"
    assert record["provider_cost_included"] is False
