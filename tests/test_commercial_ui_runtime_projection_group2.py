from decimal import Decimal

import pytest

from processual_api.billing.commercial_subscription_checkout_service import (
    CheckoutSurfaceState,
    CommercialCheckoutView,
)
from processual_api.billing.commercial_ui_runtime_projection import (
    CommercialUiPhase,
    CommercialUiSurface,
    build_commercial_ui_runtime_status,
    project_admin_marketplace,
    project_commercial_observability,
    project_customer_checkout,
)


def checkout_view(
    *,
    state: CheckoutSurfaceState = CheckoutSurfaceState.DISABLED,
    checkout_enabled: bool = False,
) -> CommercialCheckoutView:
    return CommercialCheckoutView(
        surface="customer_subscription_checkout",
        state=state,
        order_reference="order:1",
        selected_channel="local_tunisia",
        available_channels=(
            "local_tunisia",
            "lemon_squeezy",
        ),
        authoritative_price_usd=str(Decimal("29.00")),
        settlement_currency="TND",
        settlement_amount=str(Decimal("91.000")),
        customer_choice_preserved=True,
        payment_verified=False,
        activation_approved=False,
        checkout_enabled=checkout_enabled,
        provider_runtime_enabled=False,
        activation_enabled=False,
        grant_bridge_enabled=False,
        messages=("Checkout remains disabled.",),
    )


def test_checkout_projection_preserves_channel_and_price_context() -> None:
    projection = project_customer_checkout(checkout_view(state=CheckoutSurfaceState.CHANNEL_SELECTION))
    payload = projection.to_dict()

    assert projection.surface is CommercialUiSurface.CUSTOMER_CHECKOUT
    assert projection.phase is CommercialUiPhase.REVIEW
    assert {item["label"]: item["value"] for item in payload["fields"]} == {
        "USD reference price": "29.00",
        "Settlement currency": "TND",
        "Settlement amount": "91.000",
        "Selected channel": "local_tunisia",
    }
    assert projection.actions[0].enabled is False
    assert projection.actions[0].confirmation_required is True
    assert projection.actions[0].idempotency_key_required is True


@pytest.mark.parametrize(
    ("state", "phase"),
    (
        (
            CheckoutSurfaceState.PAYMENT_PENDING,
            CommercialUiPhase.PENDING,
        ),
        (
            CheckoutSurfaceState.VERIFICATION_PENDING,
            CommercialUiPhase.PENDING,
        ),
        (
            CheckoutSurfaceState.ACTIVATION_REVIEW,
            CommercialUiPhase.PENDING,
        ),
        (
            CheckoutSurfaceState.SUCCESS,
            CommercialUiPhase.SUCCESS,
        ),
        (
            CheckoutSurfaceState.ERROR,
            CommercialUiPhase.NONRETRYABLE_ERROR,
        ),
        (
            CheckoutSurfaceState.DISABLED,
            CommercialUiPhase.DISABLED,
        ),
    ),
)
def test_checkout_states_are_unambiguous(state, phase) -> None:
    assert project_customer_checkout(checkout_view(state=state)).phase is phase


def test_admin_marketplace_permission_denial_is_explicit() -> None:
    projection = project_admin_marketplace(
        phase=CommercialUiPhase.READY,
        order_reference="order:1",
        fields=(("Customer", "customer:1"),),
        permission_allowed=False,
    )

    assert projection.phase is CommercialUiPhase.PERMISSION_DENIED
    assert projection.accessibility.live_region == "assertive"
    assert projection.notices[0].code == "PLATFORM_ADMIN_REQUIRED"
    assert all(action.enabled is False for action in projection.actions)


def test_admin_marketplace_stale_and_processed_states() -> None:
    stale = project_admin_marketplace(
        phase=CommercialUiPhase.REVIEW,
        order_reference="order:1",
        fields=(),
        permission_allowed=True,
        stale_quote=True,
    )
    processed = project_admin_marketplace(
        phase=CommercialUiPhase.REVIEW,
        order_reference="order:1",
        fields=(),
        permission_allowed=True,
        already_processed=True,
    )

    assert stale.phase is CommercialUiPhase.STALE
    assert stale.notices[0].code == "STALE_QUOTE"
    assert processed.phase is CommercialUiPhase.CONFLICT
    assert processed.notices[0].code == "ALREADY_PROCESSED"


def test_observability_projection_never_mutates_or_enforces() -> None:
    projection = project_commercial_observability(
        mismatch_count=2,
        pending_activation_count=3,
        provider_replay_count=1,
    )

    assert projection.phase is CommercialUiPhase.PARTIAL
    assert projection.runtime_enabled is False
    assert projection.state_mutation_enabled is False
    assert {notice.code for notice in projection.notices} == {
        "RECONCILIATION_MISMATCH",
        "PROVIDER_REPLAY_REJECTED",
    }


def test_accessibility_and_responsive_contracts_are_governing() -> None:
    projection = project_commercial_observability(
        mismatch_count=0,
        pending_activation_count=0,
        provider_replay_count=0,
    )

    assert projection.accessibility.keyboard_navigation_required
    assert projection.accessibility.screen_reader_labels_required
    assert projection.accessibility.reduced_motion_supported
    assert projection.responsive.compact_layout_supported
    assert projection.responsive.wide_layout_supported
    assert projection.responsive.horizontal_scroll_forbidden
    assert projection.responsive.minimum_touch_target_px == 44


def test_runtime_status_remains_fail_closed() -> None:
    status = build_commercial_ui_runtime_status()

    assert status["projection_enabled"] is False
    assert status["actions_enabled"] is False
    assert status["polling_enabled"] is False
    assert status["realtime_stream_enabled"] is False
    assert status["checkout_runtime_enabled"] is False
    assert status["standalone_ui_allowed"] is False
    assert status["requires_existing_frontend_design_system"] is True
    assert status["admin_bridge"]["enabled"] is False
    assert status["provider_evidence"]["webhook_runtime_enabled"] is False
    assert status["observe_only_runtime"]["enabled"] is False


def test_negative_observation_counts_are_rejected() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        project_commercial_observability(
            mismatch_count=-1,
            pending_activation_count=0,
            provider_replay_count=0,
        )
