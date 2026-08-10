from __future__ import annotations

from hashlib import sha256

import pytest

from processual_api.billing.commercial_academic_institution_authority import (
    ACADEMIC_INSTITUTION_RUNTIME_ACTIVATION_ENABLED,
    AcademicInstitutionActivationAuthority,
    build_academic_institution_authority_status,
)
from processual_api.billing.commercial_contract_registry import (
    COMMERCIAL_CONTRACT_VERSIONS,
    build_commercial_contract_registry_status,
    commercial_contract_registry_digest,
    validate_commercial_contract_registry,
)
from processual_api.billing.commercial_state_machine import CommercialTransitionError


def test_contract_registry_is_stable_sorted_and_digestible() -> None:
    records = validate_commercial_contract_registry()

    assert [record.contract for record in records] == sorted(COMMERCIAL_CONTRACT_VERSIONS)
    assert len(records) == len(COMMERCIAL_CONTRACT_VERSIONS)

    material = "\n".join(
        f"{record.contract}={record.version}" for record in records
    )
    assert commercial_contract_registry_digest() == sha256(material.encode()).hexdigest()

    status = build_commercial_contract_registry_status()
    assert status["contract_count"] == len(records)
    assert status["runtime_enablement_changed"] is False


def test_academic_institution_authority_preserves_assessment_sources() -> None:
    authority = AcademicInstitutionActivationAuthority(
        public_plan_id="academic_institution",
        current_state="requested",
        next_state="qualified",
        assessment_reference="assessment://institution/001",
        actor_reference="operator:commercial-review",
    )

    assert authority.entitlement_codes
    status = build_academic_institution_authority_status()
    assert status["activation_requires_assessment"] is True
    assert status["quota_binding_mode"] == "assessment_required"
    assert status["price_binding_mode"] == "assessment_required"
    assert status["automatic_quota_allowed"] is False
    assert status["automatic_price_allowed"] is False
    assert status["checkout_authority_created"] is False
    assert status["payment_authority_created"] is False
    assert ACADEMIC_INSTITUTION_RUNTIME_ACTIVATION_ENABLED is False


def test_academic_institution_activation_requires_approved_quota_and_price() -> None:
    with pytest.raises(ValueError, match="assessment-approved quota"):
        AcademicInstitutionActivationAuthority(
            public_plan_id="academic_institution",
            current_state="approved",
            next_state="activated",
            assessment_reference="assessment://institution/002",
            actor_reference="operator:commercial-review",
            approved_price_reference="contract://institution/price/002",
        )

    with pytest.raises(ValueError, match="assessment-approved price"):
        AcademicInstitutionActivationAuthority(
            public_plan_id="academic_institution",
            current_state="approved",
            next_state="activated",
            assessment_reference="assessment://institution/002",
            actor_reference="operator:commercial-review",
            approved_quota_units=500_000,
        )

    authority = AcademicInstitutionActivationAuthority(
        public_plan_id="academic_institution",
        current_state="approved",
        next_state="activated",
        assessment_reference="assessment://institution/002",
        actor_reference="operator:commercial-review",
        approved_quota_units=500_000,
        approved_price_reference="contract://institution/price/002",
    )
    assert authority.approved_quota_units == 500_000


def test_academic_institution_authority_fails_closed_for_wrong_plan_and_jump() -> None:
    with pytest.raises(ValueError, match="only accepts academic_institution"):
        AcademicInstitutionActivationAuthority(
            public_plan_id="starter",
            current_state="requested",
            next_state="qualified",
            assessment_reference="assessment://bad/001",
            actor_reference="operator:test",
        )

    with pytest.raises(CommercialTransitionError):
        AcademicInstitutionActivationAuthority(
            public_plan_id="academic_institution",
            current_state="requested",
            next_state="activated",
            assessment_reference="assessment://institution/003",
            actor_reference="operator:test",
            approved_quota_units=500_000,
            approved_price_reference="contract://institution/price/003",
        )
