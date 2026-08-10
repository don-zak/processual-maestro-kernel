import asyncio

import pytest
from fastapi import HTTPException

from processual_api.billing.plan_capability_router import get_plan_capabilities


def test_academic_institution_capability_payload_is_assessment_bound() -> None:
    payload = asyncio.run(get_plan_capabilities("academic_institution"))

    assert payload["plan_code"] == "academic_institution"
    assert payload["entitlement_source_plan_code"] == "academic"
    assert payload["activation_requires_assessment"] is True
    assert payload["production_advanced_integration_allowed"] is False

    fulfillment = payload["assessment_fulfillment"]
    assert fulfillment["quota_binding_mode"] == "assessment_required"
    assert fulfillment["price_binding_mode"] == "assessment_required"
    assert fulfillment["automatic_quota_units"] is None
    assert fulfillment["automatic_monthly_price_usd"] is None

    capabilities = {item["capability_code"] for item in payload["capabilities"]}
    assert "maestro_execution" in capabilities
    assert "byok_provider_connection" in capabilities
    assert "academic_use" in capabilities


def test_unknown_plan_remains_404() -> None:
    with pytest.raises(HTTPException) as captured:
        asyncio.run(get_plan_capabilities("not-a-real-plan"))

    assert captured.value.status_code == 404
    assert captured.value.detail == "Unknown plan."
