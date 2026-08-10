import pytest

from processual_api.billing.commercial_state_machine import (
    COMMERCIAL_TRANSITIONS,
    CommercialAggregate,
    CommercialTransition,
    CommercialTransitionError,
    transition_allowed,
    validate_commercial_state_machine,
    validate_commercial_transition,
)


@pytest.mark.parametrize(
    ("aggregate", "current_state", "next_state"),
    [
        (CommercialAggregate.ORDER, "draft", "pending_payment"),
        (CommercialAggregate.PAYMENT, "pending", "verified"),
        (CommercialAggregate.SUBSCRIPTION, "pending", "active"),
        (CommercialAggregate.ASSESSMENT_ACTIVATION, "approved", "activated"),
        (CommercialAggregate.TOP_UP, "verified", "granted"),
        (CommercialAggregate.RECONCILIATION, "matched", "closed"),
    ],
)
def test_representative_allowed_transitions(
    aggregate: CommercialAggregate,
    current_state: str,
    next_state: str,
) -> None:
    transition = CommercialTransition(
        aggregate=aggregate,
        current_state=current_state,
        next_state=next_state,
        operation="test_operation",
    )

    assert transition_allowed(transition) is True
    assert validate_commercial_transition(transition) is transition


@pytest.mark.parametrize("aggregate", list(CommercialAggregate))
def test_every_commercial_aggregate_has_explicit_transition_policy(
    aggregate: CommercialAggregate,
) -> None:
    assert aggregate in COMMERCIAL_TRANSITIONS
    assert COMMERCIAL_TRANSITIONS[aggregate]


def test_unknown_transition_fails_closed() -> None:
    transition = CommercialTransition(
        aggregate=CommercialAggregate.PAYMENT,
        current_state="pending",
        next_state="settled",
        operation="settle_without_verification",
    )

    assert transition_allowed(transition) is False
    with pytest.raises(CommercialTransitionError, match="is not allowed"):
        validate_commercial_transition(transition)


def test_state_machine_rejects_self_loops() -> None:
    transition = CommercialTransition(
        aggregate=CommercialAggregate.SUBSCRIPTION,
        current_state="active",
        next_state="active",
        operation="duplicate_activation",
    )

    with pytest.raises(CommercialTransitionError, match="must change state"):
        validate_commercial_transition(transition)


def test_state_normalization_does_not_expand_authority() -> None:
    transition = CommercialTransition(
        aggregate=CommercialAggregate.ORDER,
        current_state=" DRAFT ",
        next_state=" PENDING_PAYMENT ",
        operation="submit_order",
    )

    assert transition_allowed(transition) is True


def test_transition_requires_non_blank_operation() -> None:
    with pytest.raises(ValueError, match="operation must not be blank"):
        CommercialTransition(
            aggregate=CommercialAggregate.TOP_UP,
            current_state="requested",
            next_state="pending_payment",
            operation=" ",
        )


def test_commercial_state_machine_contract_is_internally_valid() -> None:
    validate_commercial_state_machine()
