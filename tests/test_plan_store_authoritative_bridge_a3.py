from __future__ import annotations

import pytest

from processual_api.billing.plan_fulfillment_catalog import PLAN_FULFILLMENT_SPECS
from processual_api.services.plan_store import (
    DEFAULT_API_PLAN_ID,
    get_plan_policy,
    quota_limit_for_plan,
    resolve_plan_id,
)


@pytest.mark.parametrize("plan_code", tuple(PLAN_FULFILLMENT_SPECS))
def test_authoritative_plans_keep_their_identity_and_allowance(plan_code: str) -> None:
    spec = PLAN_FULFILLMENT_SPECS[plan_code]

    assert resolve_plan_id(plan_code) == plan_code
    policy = get_plan_policy(plan_code)
    assert policy["id"] == plan_code
    assert policy["source"] == "authoritative_fulfillment_catalog"
    assert quota_limit_for_plan(plan_code) == spec.monthly_unit_allowance


def test_public_enterprise_aliases_resolve_to_pilot_without_legacy_private_escalation() -> None:
    assert resolve_plan_id("enterprise") == "enterprise_pilot"
    assert resolve_plan_id("enterprise_integration") == "enterprise_pilot"
    assert quota_limit_for_plan("enterprise") == PLAN_FULFILLMENT_SPECS[
        "enterprise_pilot"
    ].monthly_unit_allowance


def test_legacy_private_plan_remains_explicit_only() -> None:
    assert resolve_plan_id("enterprise_private") == "enterprise_private"
    assert get_plan_policy("enterprise_private")["source"] == "legacy_plan"


def test_blank_plan_preserves_historical_default_only() -> None:
    assert resolve_plan_id(None) == DEFAULT_API_PLAN_ID
    assert resolve_plan_id("") == DEFAULT_API_PLAN_ID


def test_unknown_nonblank_plan_fails_closed() -> None:
    with pytest.raises(KeyError, match="unknown API quota plan"):
        resolve_plan_id("definitely_unknown_plan")


def test_starter_no_longer_collapses_to_legacy_pilot_starter() -> None:
    assert resolve_plan_id("starter") == "starter"
    assert quota_limit_for_plan("starter") == 10_000
    assert quota_limit_for_plan("pilot_starter") == 50
