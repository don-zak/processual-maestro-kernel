"""Integrated commercial UI projections for Group 2 package 3.

These presentation-safe projections compose existing checkout, Admin Marketplace,
entitlement, and observe-only contracts for consumption by the current frontend
design system. They do not create routes, render a standalone UI, mutate state,
or enable commercial runtime behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Final

from processual_api.admin_marketplace.commercial_checkout_bridge import (
    build_admin_marketplace_checkout_bridge_status,
)
from processual_api.billing.commercial_observe_only_runtime import (
    build_commercial_observe_only_status,
)
from processual_api.billing.commercial_provider_evidence_contracts import (
    build_provider_evidence_status,
)
from processual_api.billing.commercial_subscription_checkout_service import (
    CommercialCheckoutPolicy,
    CommercialCheckoutView,
)
from processual_api.billing.commercial_ui_contracts import (
    REQUIRES_EXISTING_FRONTEND_DESIGN_SYSTEM,
    STANDALONE_UI_ALLOWED,
)

COMMERCIAL_UI_RUNTIME_PROJECTION_VERSION: Final = "2026-07-group2-ui-runtime-projection-v1"
COMMERCIAL_UI_RUNTIME_PROJECTION_STATUS: Final = "draft_review"
COMMERCIAL_UI_RUNTIME_PROJECTION_ENABLED: Final = False
COMMERCIAL_UI_ACTIONS_ENABLED: Final = False
COMMERCIAL_UI_POLLING_ENABLED: Final = False
COMMERCIAL_UI_REALTIME_STREAM_ENABLED: Final = False

REQUIRES_KEYBOARD_ACCESS: Final = True
REQUIRES_SCREEN_READER_LABELS: Final = True
REQUIRES_FOCUS_MANAGEMENT: Final = True
REQUIRES_REDUCED_MOTION_SUPPORT: Final = True
REQUIRES_RESPONSIVE_LAYOUT: Final = True
REQUIRES_EXPLICIT_CONFIRMATION: Final = True
REQUIRES_IDEMPOTENCY_FEEDBACK: Final = True


class CommercialUiSurface(StrEnum):
    CUSTOMER_CHECKOUT = "customer_checkout"
    CUSTOMER_USAGE = "customer_usage"
    ADMIN_MARKETPLACE = "admin_marketplace"
    COMMERCIAL_OBSERVABILITY = "commercial_observability"


class CommercialUiPhase(StrEnum):
    LOADING = "loading"
    EMPTY = "empty"
    READY = "ready"
    REVIEW = "review"
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    CONFLICT = "conflict"
    STALE = "stale"
    RETRYABLE_ERROR = "retryable_error"
    NONRETRYABLE_ERROR = "nonretryable_error"
    PERMISSION_DENIED = "permission_denied"
    DISABLED = "disabled"


class CommercialUiSeverity(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CommercialUiAction:
    action_code: str
    label: str
    enabled: bool
    destructive: bool
    confirmation_required: bool
    idempotency_key_required: bool
    aria_label: str

    def __post_init__(self) -> None:
        for name, value in (
            ("action_code", self.action_code),
            ("label", self.label),
            ("aria_label", self.aria_label),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")
        if self.enabled:
            raise ValueError("commercial UI actions must remain disabled")


@dataclass(frozen=True, slots=True)
class CommercialUiNotice:
    severity: CommercialUiSeverity
    title: str
    message: str
    code: str
    retry_allowed: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("title", self.title),
            ("message", self.message),
            ("code", self.code),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank")


@dataclass(frozen=True, slots=True)
class CommercialAccessibilityContract:
    landmark_label: str
    heading_level: int
    live_region: str
    focus_target: str
    keyboard_navigation_required: bool
    screen_reader_labels_required: bool
    reduced_motion_supported: bool

    def __post_init__(self) -> None:
        if not self.landmark_label.strip():
            raise ValueError("landmark_label must not be blank")
        if self.heading_level not in {1, 2, 3}:
            raise ValueError("heading_level must be one, two, or three")
        if self.live_region not in {"off", "polite", "assertive"}:
            raise ValueError("live_region is invalid")
        if not self.focus_target.strip():
            raise ValueError("focus_target must not be blank")


@dataclass(frozen=True, slots=True)
class CommercialResponsiveContract:
    compact_layout_supported: bool
    wide_layout_supported: bool
    horizontal_scroll_forbidden: bool
    sticky_actions_allowed: bool
    minimum_touch_target_px: int

    def __post_init__(self) -> None:
        if self.minimum_touch_target_px < 44:
            raise ValueError("minimum touch target must be at least 44 pixels")


@dataclass(frozen=True, slots=True)
class CommercialUiProjection:
    surface: CommercialUiSurface
    phase: CommercialUiPhase
    title: str
    description: str
    primary_reference: str | None
    fields: tuple[tuple[str, str], ...]
    notices: tuple[CommercialUiNotice, ...]
    actions: tuple[CommercialUiAction, ...]
    accessibility: CommercialAccessibilityContract
    responsive: CommercialResponsiveContract
    runtime_enabled: bool
    state_mutation_enabled: bool

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if not self.description.strip():
            raise ValueError("description must not be blank")
        if self.runtime_enabled:
            raise ValueError("commercial UI runtime must remain disabled")
        if self.state_mutation_enabled:
            raise ValueError("commercial UI state mutation must remain disabled")

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["surface"] = self.surface.value
        payload["phase"] = self.phase.value
        payload["fields"] = [{"label": label, "value": value} for label, value in self.fields]
        payload["notices"] = [
            {
                **asdict(notice),
                "severity": notice.severity.value,
            }
            for notice in self.notices
        ]
        return payload


def _accessibility(
    surface: CommercialUiSurface,
    *,
    urgent: bool = False,
) -> CommercialAccessibilityContract:
    return CommercialAccessibilityContract(
        landmark_label={
            CommercialUiSurface.CUSTOMER_CHECKOUT: ("Subscription checkout"),
            CommercialUiSurface.CUSTOMER_USAGE: ("Subscription usage"),
            CommercialUiSurface.ADMIN_MARKETPLACE: ("Admin Marketplace commercial controls"),
            CommercialUiSurface.COMMERCIAL_OBSERVABILITY: ("Commercial observability"),
        }[surface],
        heading_level=1,
        live_region="assertive" if urgent else "polite",
        focus_target="commercial-surface-heading",
        keyboard_navigation_required=True,
        screen_reader_labels_required=True,
        reduced_motion_supported=True,
    )


def _responsive() -> CommercialResponsiveContract:
    return CommercialResponsiveContract(
        compact_layout_supported=True,
        wide_layout_supported=True,
        horizontal_scroll_forbidden=True,
        sticky_actions_allowed=False,
        minimum_touch_target_px=44,
    )


def project_customer_checkout(
    checkout: CommercialCheckoutView,
) -> CommercialUiProjection:
    phase = {
        "loading": CommercialUiPhase.LOADING,
        "eligibility_required": CommercialUiPhase.REVIEW,
        "channel_selection": CommercialUiPhase.REVIEW,
        "review": CommercialUiPhase.REVIEW,
        "payment_pending": CommercialUiPhase.PENDING,
        "verification_pending": CommercialUiPhase.PENDING,
        "activation_review": CommercialUiPhase.PENDING,
        "success": CommercialUiPhase.SUCCESS,
        "error": CommercialUiPhase.NONRETRYABLE_ERROR,
        "disabled": CommercialUiPhase.DISABLED,
    }[checkout.state.value]

    fields: list[tuple[str, str]] = []
    for label, value in (
        ("USD reference price", checkout.authoritative_price_usd),
        ("Settlement currency", checkout.settlement_currency),
        ("Settlement amount", checkout.settlement_amount),
        ("Selected channel", checkout.selected_channel),
    ):
        if value is not None:
            fields.append((label, value))

    notices = [
        CommercialUiNotice(
            severity=CommercialUiSeverity.INFO,
            title="Customer choice is preserved",
            message=("Eligible Tunisian customers may choose the local path or Lemon Squeezy."),
            code="CHANNEL_CHOICE_PRESERVED",
            retry_allowed=False,
        )
    ]
    if not checkout.checkout_enabled:
        notices.append(
            CommercialUiNotice(
                severity=CommercialUiSeverity.WARNING,
                title="Checkout remains disabled",
                message=("This view is available for review only and cannot create a payment session."),
                code="CHECKOUT_RUNTIME_DISABLED",
                retry_allowed=False,
            )
        )

    return CommercialUiProjection(
        surface=CommercialUiSurface.CUSTOMER_CHECKOUT,
        phase=phase,
        title="Subscription checkout",
        description=("Review plan pricing, eligibility, payment channel, and activation state."),
        primary_reference=checkout.order_reference,
        fields=tuple(fields),
        notices=tuple(notices),
        actions=(
            CommercialUiAction(
                action_code="continue_checkout",
                label="Continue",
                enabled=False,
                destructive=False,
                confirmation_required=True,
                idempotency_key_required=True,
                aria_label="Continue subscription checkout",
            ),
        ),
        accessibility=_accessibility(
            CommercialUiSurface.CUSTOMER_CHECKOUT,
            urgent=phase
            in {
                CommercialUiPhase.NONRETRYABLE_ERROR,
                CommercialUiPhase.CONFLICT,
            },
        ),
        responsive=_responsive(),
        runtime_enabled=False,
        state_mutation_enabled=False,
    )


def project_admin_marketplace(
    *,
    phase: CommercialUiPhase,
    order_reference: str | None,
    fields: tuple[tuple[str, str], ...],
    permission_allowed: bool,
    stale_quote: bool = False,
    already_processed: bool = False,
) -> CommercialUiProjection:
    if not permission_allowed:
        phase = CommercialUiPhase.PERMISSION_DENIED

    notices: list[CommercialUiNotice] = []
    if stale_quote:
        phase = CommercialUiPhase.STALE
        notices.append(
            CommercialUiNotice(
                severity=CommercialUiSeverity.WARNING,
                title="Quote has expired",
                message=("Refresh the settlement quote before reviewing the commercial decision."),
                code="STALE_QUOTE",
                retry_allowed=True,
            )
        )
    if already_processed:
        phase = CommercialUiPhase.CONFLICT
        notices.append(
            CommercialUiNotice(
                severity=CommercialUiSeverity.INFO,
                title="Order already processed",
                message=("Reload the order and review its current audit timeline before taking another action."),
                code="ALREADY_PROCESSED",
                retry_allowed=True,
            )
        )
    if not permission_allowed:
        notices.append(
            CommercialUiNotice(
                severity=CommercialUiSeverity.ERROR,
                title="Permission denied",
                message=("Only the platform administrator may access commercial decisions."),
                code="PLATFORM_ADMIN_REQUIRED",
                retry_allowed=False,
            )
        )

    actions = (
        CommercialUiAction(
            action_code="approve_activation",
            label="Approve activation",
            enabled=False,
            destructive=False,
            confirmation_required=True,
            idempotency_key_required=True,
            aria_label="Approve subscription activation",
        ),
        CommercialUiAction(
            action_code="reject_activation",
            label="Reject activation",
            enabled=False,
            destructive=True,
            confirmation_required=True,
            idempotency_key_required=True,
            aria_label="Reject subscription activation",
        ),
        CommercialUiAction(
            action_code="request_more_evidence",
            label="Request more evidence",
            enabled=False,
            destructive=False,
            confirmation_required=True,
            idempotency_key_required=True,
            aria_label="Request additional payment evidence",
        ),
    )

    return CommercialUiProjection(
        surface=CommercialUiSurface.ADMIN_MARKETPLACE,
        phase=phase,
        title="Admin Marketplace",
        description=("Review payment evidence, settlement details, activation readiness, and audit history."),
        primary_reference=order_reference,
        fields=fields,
        notices=tuple(notices),
        actions=actions,
        accessibility=_accessibility(
            CommercialUiSurface.ADMIN_MARKETPLACE,
            urgent=phase
            in {
                CommercialUiPhase.PERMISSION_DENIED,
                CommercialUiPhase.CONFLICT,
                CommercialUiPhase.NONRETRYABLE_ERROR,
            },
        ),
        responsive=_responsive(),
        runtime_enabled=False,
        state_mutation_enabled=False,
    )


def project_commercial_observability(
    *,
    mismatch_count: int,
    pending_activation_count: int,
    provider_replay_count: int,
) -> CommercialUiProjection:
    if (
        min(
            mismatch_count,
            pending_activation_count,
            provider_replay_count,
        )
        < 0
    ):
        raise ValueError("observation counts must not be negative")

    warnings = mismatch_count + provider_replay_count
    phase = CommercialUiPhase.PARTIAL if warnings > 0 else CommercialUiPhase.READY
    notices: list[CommercialUiNotice] = []
    if mismatch_count:
        notices.append(
            CommercialUiNotice(
                severity=CommercialUiSeverity.WARNING,
                title="Reconciliation mismatches detected",
                message=("Review the affected records. Automatic repair remains disabled."),
                code="RECONCILIATION_MISMATCH",
                retry_allowed=False,
            )
        )
    if provider_replay_count:
        notices.append(
            CommercialUiNotice(
                severity=CommercialUiSeverity.ERROR,
                title="Provider replays rejected",
                message=("Review provider evidence and replay keys. No commercial state was mutated."),
                code="PROVIDER_REPLAY_REJECTED",
                retry_allowed=False,
            )
        )

    return CommercialUiProjection(
        surface=CommercialUiSurface.COMMERCIAL_OBSERVABILITY,
        phase=phase,
        title="Commercial observability",
        description=("Observe checkout, activation, entitlement, and reconciliation signals without enforcement."),
        primary_reference=None,
        fields=(
            ("Reconciliation mismatches", str(mismatch_count)),
            ("Pending activations", str(pending_activation_count)),
            ("Provider replays rejected", str(provider_replay_count)),
        ),
        notices=tuple(notices),
        actions=(),
        accessibility=_accessibility(
            CommercialUiSurface.COMMERCIAL_OBSERVABILITY,
            urgent=warnings > 0,
        ),
        responsive=_responsive(),
        runtime_enabled=False,
        state_mutation_enabled=False,
    )


def build_commercial_ui_runtime_status() -> dict[str, object]:
    checkout_policy = CommercialCheckoutPolicy()
    return {
        "version": COMMERCIAL_UI_RUNTIME_PROJECTION_VERSION,
        "status": COMMERCIAL_UI_RUNTIME_PROJECTION_STATUS,
        "projection_enabled": (COMMERCIAL_UI_RUNTIME_PROJECTION_ENABLED),
        "actions_enabled": COMMERCIAL_UI_ACTIONS_ENABLED,
        "polling_enabled": COMMERCIAL_UI_POLLING_ENABLED,
        "realtime_stream_enabled": (COMMERCIAL_UI_REALTIME_STREAM_ENABLED),
        "requires_existing_frontend_design_system": (REQUIRES_EXISTING_FRONTEND_DESIGN_SYSTEM),
        "standalone_ui_allowed": STANDALONE_UI_ALLOWED,
        "keyboard_access_required": REQUIRES_KEYBOARD_ACCESS,
        "screen_reader_labels_required": (REQUIRES_SCREEN_READER_LABELS),
        "focus_management_required": REQUIRES_FOCUS_MANAGEMENT,
        "reduced_motion_support_required": (REQUIRES_REDUCED_MOTION_SUPPORT),
        "responsive_layout_required": (REQUIRES_RESPONSIVE_LAYOUT),
        "explicit_confirmation_required": (REQUIRES_EXPLICIT_CONFIRMATION),
        "idempotency_feedback_required": (REQUIRES_IDEMPOTENCY_FEEDBACK),
        "checkout_runtime_enabled": checkout_policy.enabled,
        "admin_bridge": (build_admin_marketplace_checkout_bridge_status()),
        "provider_evidence": build_provider_evidence_status(),
        "observe_only_runtime": build_commercial_observe_only_status(),
    }


__all__ = [
    "COMMERCIAL_UI_ACTIONS_ENABLED",
    "COMMERCIAL_UI_POLLING_ENABLED",
    "COMMERCIAL_UI_REALTIME_STREAM_ENABLED",
    "COMMERCIAL_UI_RUNTIME_PROJECTION_ENABLED",
    "COMMERCIAL_UI_RUNTIME_PROJECTION_STATUS",
    "COMMERCIAL_UI_RUNTIME_PROJECTION_VERSION",
    "CommercialAccessibilityContract",
    "CommercialResponsiveContract",
    "CommercialUiAction",
    "CommercialUiNotice",
    "CommercialUiPhase",
    "CommercialUiProjection",
    "CommercialUiSeverity",
    "CommercialUiSurface",
    "build_commercial_ui_runtime_status",
    "project_admin_marketplace",
    "project_commercial_observability",
    "project_customer_checkout",
]
