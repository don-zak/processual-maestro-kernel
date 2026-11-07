"""D20 public-only research evidence contract: no private imports or policy grants.

These tests protect the separation between an untrusted research projection
and general qualification. They do not purport to wire private D19 into public.
"""
from __future__ import annotations

from processual_api.cgt_governor.gateway.qualification import DynamicQualificationLayer
from processual_api.cgt_governor.gateway.trusted_evidence import (
    TrustedEvidenceBinding,
    TrustedEvidenceProjection,
    trusted_evidence_binding_issues,
)
from processual_api.cgt_governor.gateway.verification import VerificationEvidence


def test_untrusted_research_projection_has_no_default_execution_authorization():
    projection = TrustedEvidenceProjection(
        source_kind="research.metadata.unreviewed",
        source_digest="a" * 64,
        verification=VerificationEvidence(),
    )
    assert projection.execution_authorized is False
    assert projection.execution_performed is False


def test_binding_detects_replayed_research_digest():
    digest = "a" * 64
    projection = TrustedEvidenceProjection(
        source_kind="research.metadata.unreviewed",
        source_digest=digest,
        verification=VerificationEvidence(),
    )
    binding = TrustedEvidenceBinding(
        operation_id="d20-public-contract",
        consumed_source_digests=frozenset({digest}),
    )
    assert "trusted_evidence_replay_detected" in trusted_evidence_binding_issues(projection, binding)


def test_general_qualification_does_not_prove_research_authorization():
    # A baseline ranking can ALLOW if no additional evidence is required.
    # This is not authority to admit independent CGT research.
    result = DynamicQualificationLayer.qualify(rank="stable")
    assert result.recommended_action.value == "allow"
    projection = TrustedEvidenceProjection(
        source_kind="research.metadata.unreviewed",
        source_digest="b" * 64,
        verification=VerificationEvidence(),
    )
    assert not projection.execution_authorized
    assert not projection.execution_performed
