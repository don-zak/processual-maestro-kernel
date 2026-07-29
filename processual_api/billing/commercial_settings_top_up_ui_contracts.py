"""Settings-surface UI contracts for quota top-up purchase.

This module defines where and how quota top-ups must be presented in the actual
frontend. It does not implement a standalone UI or activate commercial actions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Final

from processual_api.billing.commercial_quota_top_up_contracts import (
    TopUpPolicy,
    build_top_up_policies,
    quote_top_up,
)

SETTINGS_TOP_UP_CONTRACT_VERSION: Final = "2026-07-group2-settings-top-up-v1"
SETTINGS_TOP_UP_STATUS: Final = "draft_review"

SETTINGS_TOP_UP_VISIBLE: Final = False
SETTINGS_TOP_UP_PURCHASE_ENABLED: Final = False
SETTINGS_TOP_UP_CHECKOUT_ENABLED: Final = False

STANDALONE_TOP_UP_PAGE_ALLOWED: Final = False
REQUIRES_EXISTING_SETTINGS_DESIGN_SYSTEM: Final = True


class SettingsTopUpSurface(StrEnum):
    SETTINGS_BILLING_USAGE = "settings_billing_usage"


class SettingsTopUpState(StrEnum):
    LOADING = "loading"
    READY = "ready"
    EMPTY = "empty"
    INVALID_QUANTITY = "invalid_quantity"
    UPGRADE_RECOMMENDED = "upgrade_recommended"
    PAYMENT_UNAVAILABLE = "payment_unavailable"
    PENDING = "pending"
    SUCCESS = "success"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class SettingsTopUpContent:
    heading: str
    description: str
    bundle_label: str
    quantity_label: str
    included_units_label: str
    total_units_label: str
    bundle_price_label: str
    total_price_label: str
    rollover_label: str
    upgrade_comparison_label: str
    confirmation_label: str

    def __post_init__(self) -> None:
        for value in asdict(self).values():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Settings top-up content must not contain blanks")

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


CONTENT: Final = SettingsTopUpContent(
    heading="Additional Maestro units",
    description=("Purchase additional units for the active subscription in fixed bundles."),
    bundle_label="Bundle size",
    quantity_label="Number of bundles",
    included_units_label="Current monthly allowance",
    total_units_label="Additional units",
    bundle_price_label="Price per bundle",
    total_price_label="Total price",
    rollover_label="Validity and rollover",
    upgrade_comparison_label="Compare with plan upgrade",
    confirmation_label="Review purchase",
)


@dataclass(frozen=True, slots=True)
class SettingsTopUpViewModel:
    surface: SettingsTopUpSurface
    plan_code: str
    active_subscription_required: bool
    controlled_stepper_required: bool
    free_form_quantity_allowed: bool
    policy: dict[str, Any]
    content: dict[str, str]
    states: tuple[str, ...]
    visible: bool
    purchase_enabled: bool
    checkout_enabled: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["surface"] = self.surface.value
        payload["states"] = list(self.states)
        return payload


def build_settings_top_up_view_model(plan_code: str) -> SettingsTopUpViewModel:
    policies: dict[str, TopUpPolicy] = {policy.plan_code: policy for policy in build_top_up_policies()}
    if plan_code not in policies:
        raise ValueError(f"Unknown settings top-up plan: {plan_code}")

    policy = policies[plan_code]

    return SettingsTopUpViewModel(
        surface=SettingsTopUpSurface.SETTINGS_BILLING_USAGE,
        plan_code=plan_code,
        active_subscription_required=True,
        controlled_stepper_required=True,
        free_form_quantity_allowed=False,
        policy=policy.to_dict(),
        content=CONTENT.to_dict(),
        states=tuple(state.value for state in SettingsTopUpState),
        visible=SETTINGS_TOP_UP_VISIBLE,
        purchase_enabled=SETTINGS_TOP_UP_PURCHASE_ENABLED,
        checkout_enabled=SETTINGS_TOP_UP_CHECKOUT_ENABLED,
    )


def build_settings_top_up_preview(
    plan_code: str,
    requested_units: int,
) -> dict[str, Any]:
    view = build_settings_top_up_view_model(plan_code)
    quote = quote_top_up(plan_code, requested_units)
    return {
        "contract_version": SETTINGS_TOP_UP_CONTRACT_VERSION,
        "status": SETTINGS_TOP_UP_STATUS,
        "surface": view.surface.value,
        "view": view.to_dict(),
        "quote": quote.to_dict(),
        "standalone_page_allowed": STANDALONE_TOP_UP_PAGE_ALLOWED,
        "requires_existing_settings_design_system": (REQUIRES_EXISTING_SETTINGS_DESIGN_SYSTEM),
    }
