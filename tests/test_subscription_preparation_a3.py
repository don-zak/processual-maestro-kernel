import asyncio
import uuid
from types import SimpleNamespace

import pytest

from processual_api.billing.subscription_preparation import (
    build_subscription_preparation,
)

USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


class FakeRepository:
    def __init__(self, intent):
        self.intent = intent
        self.requested_user_id = None

    async def registration_plan_intent_for_user(self, *, user_id):
        self.requested_user_id = user_id
        return self.intent


def _build(intent):
    repository = FakeRepository(intent)
    result = asyncio.run(
        build_subscription_preparation(
            repository=repository,
            user_id=USER_ID,
        )
    )
    assert repository.requested_user_id == USER_ID
    return result


def test_subscription_preparation_returns_no_intent():
    assert _build(None) == {
        "status": "no_intent",
        "checkout_available": False,
    }


def test_subscription_preparation_returns_pending_verification():
    result = _build(
        SimpleNamespace(
            state="pending_verification",
            selected_plan_id="starter",
            billing_period="monthly",
        )
    )

    assert result == {
        "status": "pending_verification",
        "checkout_available": False,
    }


@pytest.mark.parametrize("state", ["cancelled", "superseded"])
def test_subscription_preparation_rejects_inactive_intent(state):
    result = _build(
        SimpleNamespace(
            state=state,
            selected_plan_id="starter",
            billing_period="monthly",
        )
    )

    assert result == {
        "status": "invalid_intent",
        "checkout_available": False,
    }


@pytest.mark.parametrize("billing_period", [None, "weekly"])
def test_subscription_preparation_rejects_invalid_billing_period(
    billing_period,
):
    result = _build(
        SimpleNamespace(
            state="verified",
            selected_plan_id="starter",
            billing_period=billing_period,
        )
    )

    assert result == {
        "status": "invalid_intent",
        "checkout_available": False,
    }


@pytest.mark.parametrize("billing_period", ["monthly", "annual"])
def test_subscription_preparation_returns_verified_direct_plan(
    billing_period,
):
    result = _build(
        SimpleNamespace(
            state="verified",
            selected_plan_id="starter",
            billing_period=billing_period,
        )
    )

    assert result["status"] == "verified"
    assert result["plan_id"] == "starter"
    assert result["billing_period"] == billing_period
    assert result["display_name"]
    assert result["price_usd"] is not None
    assert result["currency"] == "USD"
    assert result["included_quota_units"] is not None
    assert result["checkout_available"] is False


def test_subscription_preparation_rejects_unknown_plan():
    result = _build(
        SimpleNamespace(
            state="verified",
            selected_plan_id="unknown-plan",
            billing_period="monthly",
        )
    )

    assert result == {
        "status": "invalid_intent",
        "checkout_available": False,
    }


def test_subscription_preparation_rejects_assessment_plan():
    result = _build(
        SimpleNamespace(
            state="verified",
            selected_plan_id="enterprise_integration_starter",
            billing_period="annual",
        )
    )

    assert result == {
        "status": "invalid_intent",
        "checkout_available": False,
    }
