"""Strict shared runtime: reject ALL legacy governance paths before any core work."""
import asyncio
import pytest
from processual_kernel import (
    AgentSpec, AgentTelemetry, HandoffTelemetry, WorkflowTelemetry,
    ProcessualMaestroKernel, MaestroAction, TaskEnvelope)
from processual_kernel.admission_port import GovernanceEvidenceUnavailable

def test_strict_mode_blocks_all_raw_admission_bypasses_before_state_mutation(monkeypatch):
    kernel=ProcessualMaestroKernel(enforce_evidence_admission=True)
    kernel.register_agent(AgentSpec("a","planner",capabilities=("plan",)))
    before=kernel.maestro_snapshot()
    def should_not_run(*a,**kw):
        raise AssertionError("CORE_CALLED_BEFORE_SIGNED_DATA_ADMISSION")
    monkeypatch.setattr(kernel.cgt,"evaluate_transition",should_not_run)
    monkeypatch.setattr(kernel.continuity,"step",should_not_run)
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        kernel.observe("a",AgentTelemetry())
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        kernel.observe_handoff("a","b",HandoffTelemetry())
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        kernel.observe_workflow("w",WorkflowTelemetry())
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        kernel.route_candidates(TaskEnvelope(task_id="t",required_capability="plan",payload={}))
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        kernel.intervene("w",MaestroAction.REROUTE,"s","unqualified")
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        asyncio.run(kernel.run_task(TaskEnvelope(task_id="t",required_capability="plan",payload={})))
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        asyncio.run(kernel.run_workflow("w"))
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        kernel.register_agent(AgentSpec("b","worker"),initial_telemetry=AgentTelemetry())
    assert kernel.maestro_snapshot()==before

def test_runtime_strict_mode_is_environment_configurable(monkeypatch):
    monkeypatch.setenv("PROCESSUAL_GOVERNANCE_EVIDENCE_REQUIRED","true")
    k=ProcessualMaestroKernel()
    assert k.enforce_evidence_admission
    with pytest.raises(GovernanceEvidenceUnavailable):
        k.observe("nonexistent",AgentTelemetry())
    # Enforced by the environment: a caller cannot opt out.
    assert ProcessualMaestroKernel(enforce_evidence_admission=False).enforce_evidence_admission
    monkeypatch.delenv("PROCESSUAL_GOVERNANCE_EVIDENCE_REQUIRED")
    assert not ProcessualMaestroKernel(enforce_evidence_admission=False).enforce_evidence_admission

def test_production_cannot_disable_gate_even_with_explicit_false(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT","production")
    monkeypatch.delenv("PROCESSUAL_GOVERNANCE_EVIDENCE_REQUIRED",raising=False)
    k=ProcessualMaestroKernel(enforce_evidence_admission=False)
    assert k.enforce_evidence_admission
    with pytest.raises(GovernanceEvidenceUnavailable,match="raw_telemetry_governance_forbidden"):
        k.observe("unknown",AgentTelemetry())
