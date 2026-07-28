from dataclasses import replace

import pytest

from processual_api.billing.maestro_execution_authority import (
    MaestroExecutionAuthorityKind,
)
from processual_api.billing.maestro_execution_authority_readiness import (
    MaestroReadinessCapabilityStatus,
)
from processual_api.billing.maestro_execution_family_evidence import (
    AGENT_RUNTIME_EVIDENCE,
    AUTH_DELIVERY_EVIDENCE,
    CONNECTOR_SANDBOX_EVIDENCE,
    EXECUTION_FAMILY_EVIDENCE_CATALOG,
    LLM_ADAPTER_EVIDENCE,
    MaestroCommercialWorkloadClassification,
    MaestroExecutionEvidenceClassification,
    MaestroExecutionFamilyEvidenceValidationError,
    commercial_measurement_ready_families,
    get_execution_family_evidence,
)


def test_catalog_contains_expected_families() -> None:
    assert {item.family_id for item in EXECUTION_FAMILY_EVIDENCE_CATALOG} == {
        "auth.delivery_dispatch",
        "agent.runtime_adapter",
        "cgt_governor.llm_adapter",
        "integrations.connector_sandbox_read",
    }


def test_catalog_family_ids_are_unique() -> None:
    family_ids = [item.family_id for item in EXECUTION_FAMILY_EVIDENCE_CATALOG]

    assert len(family_ids) == len(set(family_ids))


def test_auth_delivery_is_production_but_non_billable() -> None:
    assert AUTH_DELIVERY_EVIDENCE.evidence_classification is MaestroExecutionEvidenceClassification.PRODUCTION
    assert (
        AUTH_DELIVERY_EVIDENCE.commercial_classification
        is MaestroCommercialWorkloadClassification.NON_BILLABLE_PLATFORM
    )
    assert AUTH_DELIVERY_EVIDENCE.authority_kind is MaestroExecutionAuthorityKind.DELIVERY_DISPATCH
    assert AUTH_DELIVERY_EVIDENCE.commercial_measurement_ready is False


def test_agent_runtime_is_abstract_and_not_ready() -> None:
    assert AGENT_RUNTIME_EVIDENCE.evidence_classification is MaestroExecutionEvidenceClassification.ABSTRACT_CONTRACT
    assert AGENT_RUNTIME_EVIDENCE.readiness.is_ready is False
    assert AGENT_RUNTIME_EVIDENCE.commercial_measurement_ready is False


def test_llm_adapter_is_candidate_but_fails_closed() -> None:
    assert (
        LLM_ADAPTER_EVIDENCE.commercial_classification is MaestroCommercialWorkloadClassification.COMMERCIAL_CANDIDATE
    )
    assert LLM_ADAPTER_EVIDENCE.evidence_classification is MaestroExecutionEvidenceClassification.PARTIAL_PRODUCTION
    assert LLM_ADAPTER_EVIDENCE.readiness.is_ready is False
    assert LLM_ADAPTER_EVIDENCE.commercial_measurement_ready is False


def test_connector_sandbox_is_synthetic_and_not_eligible() -> None:
    assert CONNECTOR_SANDBOX_EVIDENCE.evidence_classification is MaestroExecutionEvidenceClassification.SYNTHETIC_ONLY
    assert CONNECTOR_SANDBOX_EVIDENCE.commercial_classification is MaestroCommercialWorkloadClassification.NOT_ELIGIBLE
    assert (
        CONNECTOR_SANDBOX_EVIDENCE.readiness.production_classification
        is MaestroReadinessCapabilityStatus.SYNTHETIC_ONLY
    )
    assert CONNECTOR_SANDBOX_EVIDENCE.commercial_measurement_ready is False


def test_no_family_is_commercially_ready() -> None:
    assert commercial_measurement_ready_families() == ()


def test_lookup_returns_known_family() -> None:
    assert get_execution_family_evidence("auth.delivery_dispatch") is AUTH_DELIVERY_EVIDENCE


def test_lookup_returns_none_for_unknown_family() -> None:
    assert get_execution_family_evidence("unknown.family") is None


def test_synthetic_family_cannot_be_commercial_candidate() -> None:
    with pytest.raises(
        MaestroExecutionFamilyEvidenceValidationError,
        match="synthetic-only evidence",
    ):
        replace(
            CONNECTOR_SANDBOX_EVIDENCE,
            commercial_classification=(MaestroCommercialWorkloadClassification.COMMERCIAL_CANDIDATE),
        )


def test_readiness_authority_must_match_family_authority() -> None:
    with pytest.raises(
        MaestroExecutionFamilyEvidenceValidationError,
        match="readiness authority_kind",
    ):
        replace(
            AGENT_RUNTIME_EVIDENCE,
            readiness=LLM_ADAPTER_EVIDENCE.readiness,
        )


def test_missing_capabilities_must_be_unique() -> None:
    with pytest.raises(
        MaestroExecutionFamilyEvidenceValidationError,
        match="must not contain duplicates",
    ):
        replace(
            AGENT_RUNTIME_EVIDENCE,
            missing_capabilities=("execution_id", "execution_id"),
        )
