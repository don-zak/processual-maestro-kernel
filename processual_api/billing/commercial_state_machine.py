from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class CommercialAggregate(StrEnum):
    ORDER = "order"
    PAYMENT = "payment"
    SUBSCRIPTION = "subscription"
    ASSESSMENT_ACTIVATION = "assessment_activation"
    TOP_UP = "top_up"
    RECONCILIATION = "reconciliation"


class CommercialTransitionError(ValueError):
    """Raised when a commercial aggregate transition is not explicitly allowed."""


@dataclass(frozen=True, slots=True)
class CommercialTransition:
    aggregate: CommercialAggregate
    current_state: str
    next_state: str
    operation: str

    def __post_init__(self) -> None:
        if not self.current_state.strip():
            raise ValueError("current_state must not be blank")
        if not self.next_state.strip():
            raise ValueError("next_state must not be blank")
        if not self.operation.strip():
            raise ValueError("operation must not be blank")


_TRANSITIONS: dict[CommercialAggregate, frozenset[tuple[str, str]]] = {
    CommercialAggregate.ORDER: frozenset(
        {
            ("draft", "pending_payment"),
            ("pending_payment", "paid"),
            ("pending_payment", "cancelled"),
            ("paid", "fulfilled"),
            ("paid", "refunded"),
        }
    ),
    CommercialAggregate.PAYMENT: frozenset(
        {
            ("pending", "verified"),
            ("pending", "failed"),
            ("verified", "settled"),
            ("verified", "refunded"),
        }
    ),
    CommercialAggregate.SUBSCRIPTION: frozenset(
        {
            ("pending", "active"),
            ("active", "suspended"),
            ("suspended", "active"),
            ("active", "cancelled"),
            ("suspended", "cancelled"),
            ("active", "expired"),
        }
    ),
    CommercialAggregate.ASSESSMENT_ACTIVATION: frozenset(
        {
            ("requested", "qualified"),
            ("qualified", "approved"),
            ("approved", "activated"),
            ("requested", "rejected"),
            ("qualified", "rejected"),
            ("approved", "revoked"),
            ("activated", "revoked"),
        }
    ),
    CommercialAggregate.TOP_UP: frozenset(
        {
            ("requested", "pending_payment"),
            ("pending_payment", "verified"),
            ("pending_payment", "cancelled"),
            ("verified", "granted"),
            ("verified", "refunded"),
        }
    ),
    CommercialAggregate.RECONCILIATION: frozenset(
        {
            ("open", "matched"),
            ("open", "exception"),
            ("exception", "matched"),
            ("matched", "closed"),
        }
    ),
}

COMMERCIAL_TRANSITIONS: Final = MappingProxyType(_TRANSITIONS)


def normalize_commercial_state(value: str) -> str:
    return str(value or "").strip().lower()


def transition_allowed(transition: CommercialTransition) -> bool:
    current_state = normalize_commercial_state(transition.current_state)
    next_state = normalize_commercial_state(transition.next_state)
    return (current_state, next_state) in COMMERCIAL_TRANSITIONS[transition.aggregate]


def validate_commercial_transition(transition: CommercialTransition) -> CommercialTransition:
    current_state = normalize_commercial_state(transition.current_state)
    next_state = normalize_commercial_state(transition.next_state)

    if current_state == next_state:
        raise CommercialTransitionError(
            f"commercial transition must change state: {transition.aggregate.value} {current_state}"
        )

    if not transition_allowed(transition):
        raise CommercialTransitionError(
            "commercial transition is not allowed: "
            f"{transition.aggregate.value} {current_state}->{next_state} "
            f"operation={transition.operation}"
        )
    return transition


def validate_commercial_state_machine() -> None:
    for aggregate, transitions in COMMERCIAL_TRANSITIONS.items():
        if not transitions:
            raise ValueError(f"commercial aggregate has no transition policy: {aggregate.value}")
        for current_state, next_state in transitions:
            if not current_state or not next_state:
                raise ValueError(
                    f"commercial transition contains blank state: {aggregate.value}"
                )
            if current_state == next_state:
                raise ValueError(
                    f"commercial transition contains self-loop: {aggregate.value} {current_state}"
                )


validate_commercial_state_machine()


__all__ = [
    "COMMERCIAL_TRANSITIONS",
    "CommercialAggregate",
    "CommercialTransition",
    "CommercialTransitionError",
    "normalize_commercial_state",
    "transition_allowed",
    "validate_commercial_state_machine",
    "validate_commercial_transition",
]
