from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from processual_api.admin_marketplace.authority import (
    AdminMarketplaceAuthorityContext,
)
from processual_api.admin_marketplace.commercial_offer_lifecycle import (
    apply_offer_lifecycle_transition,
    evaluate_offer_lifecycle_transition,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceStepUpRequiredError,
)

NOW = datetime(2026, 8, 17, 13, 30, tzinfo=UTC)
OFFER_ID = "offer-001"


def _authority(*, mfa: bool = True) -> AdminMarketplaceAuthorityContext:
    return AdminMarketplaceAuthorityContext(
        user_id="user-001",
        session_id="session-001",
        platform_authorities=frozenset({"platform_admin"}),
        active_platform_admin=True,
        recent_mfa_step_up=mfa,
    )


def _lemon_offer(**changes: object) -> SimpleNamespace:
    values = {
        "id": OFFER_ID,
        "status": "approved",
        "sales_channel": "lemon_squeezy",
        "updated_at": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _binding(**changes: object) -> SimpleNamespace:
    values = {
        "offer_id": OFFER_ID,
        "provider": "lemon_squeezy",
        "provider_variant_id": "variant-001",
        "status": "verified",
        "verification_reference": "verify-001",
        "verified_at": NOW,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def test_offer_review_and_approval_transitions_are_explicit() -> None:
    review = evaluate_offer_lifecycle_transition(
        current_status="draft",
        target_status="under_review",
        authority=_authority(),
    )
    approved = evaluate_offer_lifecycle_transition(
        current_status="under_review",
        target_status="approved",
        authority=_authority(),
    )

    assert review.allowed is True
    assert approved.allowed is True


def test_publication_is_blocked_until_canonical_provenance_is_verified() -> None:
    decision = evaluate_offer_lifecycle_transition(
        current_status="approved",
        target_status="published",
        authority=_authority(),
        canonical_projection_verified=False,
    )

    assert decision.allowed is False
    assert decision.reason_code == "canonical_projection_provenance_required"


def test_verified_canonical_offer_can_transition_from_approved_to_published() -> None:
    decision = evaluate_offer_lifecycle_transition(
        current_status="approved",
        target_status="published",
        authority=_authority(),
        canonical_projection_verified=True,
    )

    assert decision.allowed is True
    assert decision.reason_code == "offer_status_transition_allowed"


def test_lemon_publication_is_blocked_without_verified_provider_binding() -> None:
    offer = _lemon_offer()

    decision = apply_offer_lifecycle_transition(
        offer=offer,
        target_status="published",
        authority=_authority(),
        now=NOW,
        canonical_projection_verified=True,
    )

    assert decision.allowed is False
    assert decision.reason_code == "verified_provider_binding_required"
    assert offer.status == "approved"
    assert offer.updated_at is None


def test_lemon_publication_is_blocked_for_pending_provider_binding() -> None:
    offer = _lemon_offer()
    binding = _binding(
        status="pending",
        verification_reference=None,
        verified_at=None,
    )

    decision = apply_offer_lifecycle_transition(
        offer=offer,
        target_status="published",
        authority=_authority(),
        now=NOW,
        canonical_projection_verified=True,
        provider_binding=binding,
    )

    assert decision.allowed is False
    assert decision.reason_code == "verified_provider_binding_required"
    assert offer.status == "approved"


def test_lemon_publication_is_blocked_for_binding_from_another_offer() -> None:
    offer = _lemon_offer()
    binding = _binding(offer_id="offer-002")

    decision = apply_offer_lifecycle_transition(
        offer=offer,
        target_status="published",
        authority=_authority(),
        now=NOW,
        canonical_projection_verified=True,
        provider_binding=binding,
    )

    assert decision.allowed is False
    assert decision.reason_code == "verified_provider_binding_required"
    assert offer.status == "approved"


def test_verified_lemon_binding_allows_publication() -> None:
    offer = _lemon_offer()

    decision = apply_offer_lifecycle_transition(
        offer=offer,
        target_status="published",
        authority=_authority(),
        now=NOW,
        canonical_projection_verified=True,
        provider_binding=_binding(),
    )

    assert decision.allowed is True
    assert decision.reason_code == "offer_status_transition_allowed"
    assert offer.status == "published"
    assert offer.updated_at == NOW


def test_non_lemon_publication_does_not_require_lemon_binding() -> None:
    offer = _lemon_offer(sales_channel="maestro_direct")

    decision = apply_offer_lifecycle_transition(
        offer=offer,
        target_status="published",
        authority=_authority(),
        now=NOW,
        canonical_projection_verified=True,
    )

    assert decision.allowed is True
    assert offer.status == "published"


def test_publication_requires_recent_mfa_before_provenance_is_considered() -> None:
    with pytest.raises(AdminMarketplaceStepUpRequiredError):
        evaluate_offer_lifecycle_transition(
            current_status="approved",
            target_status="published",
            authority=_authority(mfa=False),
            canonical_projection_verified=True,
        )


def test_retired_offer_cannot_be_reactivated() -> None:
    decision = evaluate_offer_lifecycle_transition(
        current_status="retired",
        target_status="under_review",
        authority=_authority(),
    )

    assert decision.allowed is False
    assert decision.reason_code == "offer_status_transition_not_allowed"


def test_allowed_transition_mutates_only_status_and_update_time() -> None:
    offer = SimpleNamespace(status="draft", updated_at=None, amount="49.000")

    decision = apply_offer_lifecycle_transition(
        offer=offer,
        target_status="under_review",
        authority=_authority(),
        now=NOW,
    )

    assert decision.allowed is True
    assert offer.status == "under_review"
    assert offer.updated_at == NOW
    assert offer.amount == "49.000"


def test_naive_lifecycle_clock_is_rejected() -> None:
    offer = SimpleNamespace(status="draft", updated_at=None)

    with pytest.raises(ValueError, match="timezone-aware"):
        apply_offer_lifecycle_transition(
            offer=offer,
            target_status="under_review",
            authority=_authority(),
            now=datetime(2026, 8, 17, 13, 30),
        )
