from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from processual_api.cgt_governor.gateway.governance_context import GovernanceRequestContext
from processual_api.cgt_governor.gateway.governance_genome import (
    EvidenceLevel,
    GovernanceGate,
    governance_genome,
)
from processual_api.cgt_governor.gateway.models import Agent, AgentState, GatewayAction
from processual_api.cgt_governor.gateway.operation_policies import get_operation_policy
from processual_api.cgt_governor.gateway.registry import AgentRegistry
from processual_api.cgt_governor.gateway.runtime_execution_attestation import (
    build_runtime_execution_attestation,
    runtime_attestation_issues,
)
from processual_api.cgt_governor.gateway.storage import MemoryStorage
from processual_api.cgt_governor.gateway.sufficiency import (
    SufficiencyStatus,
    TaskSufficiencyEvidence,
)
from processual_api.cgt_governor.gateway.trusted_evidence import (
    TrustedEvidenceBinding,
    TrustedEvidenceProjection,
)
from processual_api.cgt_governor.gateway.verification import (
    VerificationEvidence,
    VerificationStatus,
)
from processual_api.cgt_governor.policy.engine import GovernanceAction, PolicyEngine


def _agent(*, tags: list[str] | None = None) -> Agent:
    now = datetime.now(UTC).isoformat()
    return Agent(
        agent_id="public-governance-agent",
        name="Public Governance Agent",
        role="worker",
        adapter_name="test",
        model="test-model",
        system_prompt="",
        language="en",
        state=AgentState.ACTIVE,
        created_at=now,
        last_state_change=now,
        last_state_reason="test",
        tags=tags or [],
    )


def _scores() -> dict[str, float]:
    return {
        "compatibility": 0.9,
        "coherence": 0.9,
        "structural_support": 0.9,
        "usefulness": 0.9,
        "complexity": 0.1,
        "fatigue": 0.0,
        "shock": 0.0,
        "lift": 0.8,
        "novelty": 0.5,
        "no_answer": 0.0,
        "hallucination": 0.0,
        "constraint_failure": 0.0,
        "speed": 0.5,
    }


def _stable_result():
    return SimpleNamespace(
        fate=SimpleNamespace(
            stability=0.8,
            hybridity=0.1,
            distortion=0.0,
            extinction=0.0,
            collapse=0.0,
            flourishing=0.6,
            transient=0.0,
        ),
        rank=SimpleNamespace(value="stable"),
        reward=0.9,
        policy="accept",
        policy_label="Stable",
        repair_prompt=None,
    )


def _wire(monkeypatch, *, tags: list[str] | None = None):
    from processual_api.cgt_governor import analyzer, governor
    from processual_api.cgt_governor.gateway import engine as engine_module

    registry = AgentRegistry(storage=MemoryStorage())
    registry.register(_agent(tags=tags))
    monkeypatch.setattr(analyzer, "analyze_cgt", lambda *args, **kwargs: _scores())
    monkeypatch.setattr(governor, "govern_answer", lambda *args, **kwargs: _stable_result())
    monkeypatch.setattr(engine_module, "gateway_registry", registry)
    monkeypatch.setattr(engine_module, "sign_response", lambda payload: "sig")
    monkeypatch.setattr(engine_module.lifecycle_engine, "evaluate_agent", lambda current_agent: None)
    return engine_module, registry


def test_public_genome_is_fail_closed_and_capped_at_e4() -> None:
    assert governance_genome.default_fail_closed is True
    assert governance_genome.runtime_claim_ceiling == EvidenceLevel.E4_CROSSFIT_QUALIFIED
    assert governance_genome.precedence[:3] == (
        GovernanceGate.CONSTITUTIVE_CONSTRAINT,
        GovernanceGate.AUTHORIZATION,
        GovernanceGate.EVIDENCE,
    )


def test_sensitive_public_operation_requires_server_owned_runtime_attestation() -> None:
    policy = get_operation_policy("sandbox.activate")
    assert policy is not None
    assert policy.required_scopes == ("sandbox:activate",)
    assert policy.require_factual_evidence is True
    assert policy.require_execution_evidence is True
    assert policy.require_task_sufficiency is True
    assert policy.require_runtime_attestation is True


def test_missing_scope_blocks_stable_response(monkeypatch) -> None:
    engine_module, _ = _wire(monkeypatch, tags=["scope:read"])
    decision = engine_module.GatewayEngine.evaluate(
        "public-governance-agent",
        "q",
        "a",
        governance_context=GovernanceRequestContext(required_scopes=("write",)),
    )
    assert decision is not None
    assert decision.action == GatewayAction.BLOCK
    assert decision.governance_gate == "authorization"


def test_unknown_operation_fails_closed(monkeypatch) -> None:
    engine_module, _ = _wire(monkeypatch, tags=["scope:read"])
    decision = engine_module.GatewayEngine.evaluate(
        "public-governance-agent",
        "q",
        "a",
        operation_id="unknown.operation",
    )
    assert decision is not None
    assert decision.action == GatewayAction.BLOCK
    assert decision.governance_gate == "authorization"


def test_sandbox_requires_final_runtime_attestation(monkeypatch) -> None:
    engine_module, _ = _wire(monkeypatch, tags=["scope:sandbox:activate"])
    source_digest = "a" * 64

    decision = engine_module.GatewayEngine.evaluate(
        "public-governance-agent",
        "q",
        "a",
        operation_id="sandbox.activate",
        trusted_evidence_projection=TrustedEvidenceProjection(
            source_kind="public.precondition",
            source_digest=source_digest,
            verification=VerificationEvidence(
                factual=VerificationStatus.VERIFIED,
                execution=VerificationStatus.VERIFIED,
            ),
        ),
        trusted_evidence_binding=TrustedEvidenceBinding(
            operation_id="sandbox.activate",
        ),
        sufficiency_evidence=TaskSufficiencyEvidence(
            status=SufficiencyStatus.SUFFICIENT,
        ),
    )
    assert decision is not None
    assert decision.action == GatewayAction.BLOCK
    assert decision.governance_gate == "evidence"


def test_sandbox_passes_when_entire_public_execution_lineage_is_valid(monkeypatch) -> None:
    engine_module, _ = _wire(monkeypatch, tags=["scope:sandbox:activate"])
    source_digest = "b" * 64
    attestation = build_runtime_execution_attestation(
        operation_id="sandbox.activate",
        actor_ref="runtime-worker-1",
        execution_reference_id="exec-1",
        source_digest=source_digest,
        performed_at="2026-09-18T19:00:00+00:00",
        attested_at="2026-09-18T19:00:01+00:00",
        succeeded=True,
    )

    decision = engine_module.GatewayEngine.evaluate(
        "public-governance-agent",
        "q",
        "a",
        operation_id="sandbox.activate",
        trusted_evidence_projection=TrustedEvidenceProjection(
            source_kind="public.precondition",
            source_digest=source_digest,
            verification=VerificationEvidence(
                factual=VerificationStatus.VERIFIED,
                execution=VerificationStatus.UNVERIFIED,
            ),
        ),
        trusted_evidence_binding=TrustedEvidenceBinding(
            operation_id="sandbox.activate",
        ),
        runtime_execution_attestation=attestation,
        sufficiency_evidence=TaskSufficiencyEvidence(
            status=SufficiencyStatus.SUFFICIENT,
        ),
    )
    assert decision is not None
    assert decision.action == GatewayAction.PASS
    assert decision.governance_gate is None
    assert decision.qualification is not None
    assert decision.qualification["runtime_execution_attestation"]["succeeded"] is True


def test_runtime_attestation_operation_mismatch_is_detected() -> None:
    attestation = build_runtime_execution_attestation(
        operation_id="sandbox.activate",
        actor_ref="runtime-worker-1",
        execution_reference_id="exec-2",
        source_digest="c" * 64,
        performed_at="2026-09-18T19:00:00+00:00",
        attested_at="2026-09-18T19:00:01+00:00",
        succeeded=True,
    )
    issues = runtime_attestation_issues(
        attestation,
        operation_id="api_key.issue",
        evaluated_at="2026-09-18T20:00:00+00:00",
    )
    assert "runtime_attestation_operation_mismatch" in issues


def test_runtime_policy_reflects_gateway_block_instead_of_redeciding() -> None:
    decision = PolicyEngine().reflect_gateway_decision(
        gateway_action="block",
        agent_state="active",
        rank="stable",
        reward=1.0,
        policy="accept",
        policy_label="Authorization Boundary - Fail Closed",
    )
    assert decision.action == GovernanceAction.reject
