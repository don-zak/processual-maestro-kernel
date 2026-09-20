from __future__ import annotations

import math

import pytest

from processual_kernel import (
    AgentSpec,
    AgentTelemetry,
    Coefficients,
    HandoffTelemetry,
    ProcessualCGTKernel,
    ProcessualMaestroKernel,
    PsiV2Engine,
    PsiV2Parameters,
    WorkflowPlan,
    WorkflowStep,
    WorkflowTelemetry,
)


def test_psi_v2_drive_matches_legacy_integrand_without_dt() -> None:
    coeff = Coefficients(T=0.8, N=0.75, C=0.2, M=0.3)
    expected = ((0.8 * 0.75) - 0.2) * math.exp(-0.3)
    assert PsiV2Engine.drive(coeff) == pytest.approx(expected)


def test_psi_v2_converges_under_constant_positive_drive() -> None:
    engine = PsiV2Engine(PsiV2Parameters(dt=1.0, decay_lambda=0.1))
    coeff = Coefficients(T=1.0, N=1.0, C=0.0, M=0.0)
    state = None
    for _ in range(500):
        state = engine.advance(state, coeff)
    assert state is not None
    assert state.psi == pytest.approx(10.0, rel=1e-6)
    assert abs(state.dpsi) < 1e-8


def test_positive_drive_can_coexist_with_negative_dpsi() -> None:
    engine = PsiV2Engine(PsiV2Parameters(dt=1.0, decay_lambda=0.2))
    coeff = Coefficients(T=1.0, N=1.0, C=0.0, M=0.0)
    state = engine.step(10.0, coeff)
    assert state.drive == pytest.approx(1.0)
    assert state.dpsi == pytest.approx(-1.0)
    assert state.psi == pytest.approx(9.0)


def test_parameter_guard_rejects_unstable_explicit_step() -> None:
    with pytest.raises(ValueError, match=r"decay_lambda \* dt"):
        PsiV2Parameters(dt=2.0, decay_lambda=0.6)


def test_agent_shadow_does_not_change_legacy_snapshot_contract_or_decision() -> None:
    kernel = ProcessualCGTKernel()
    kernel.register_agent(AgentSpec(agent_id="a", role="worker", capabilities=("x",)))
    before_keys = set(kernel.snapshot()[0].keys())
    telemetry = AgentTelemetry(
        success_rate=0.9,
        cooperation_success=0.8,
        useful_handoff_rate=0.8,
        demand_rate=0.8,
        business_priority=0.8,
        resource_cost=0.1,
    )
    coeff = kernel.mapper.from_agent_telemetry(telemetry)
    expected_psi, expected_dpsi = kernel.continuity.step(0.0, coeff)
    decision = kernel.observe("a", telemetry)
    assert decision.psi == pytest.approx(expected_psi)
    assert decision.dpsi == pytest.approx(expected_dpsi)
    assert set(kernel.snapshot()[0].keys()) == before_keys
    shadow = kernel.psi_v2_shadow_snapshot()["agents"]["a"]
    assert shadow is not None
    assert shadow["drive"] == pytest.approx(PsiV2Engine.drive(coeff))


def test_handoff_and_workflow_shadow_are_separate_from_legacy_snapshot() -> None:
    kernel = ProcessualMaestroKernel()
    edge = kernel.observe_handoff("a", "b", HandoffTelemetry(
        artifact_quality=0.9,
        context_preservation=0.9,
        acceptance_rate=0.9,
        rework_rate=0.05,
        ambiguity=0.05,
        demand_rate=0.8,
    ))
    kernel.create_workflow(WorkflowPlan(
        workflow_id="wf",
        goal="shadow qualification",
        steps=(WorkflowStep(step_id="s1", capability="x", instruction="run"),),
    ))
    workflow = kernel.observe_workflow(
        "wf",
        WorkflowTelemetry(
            goal_alignment=0.9,
            progress_rate=0.4,
            completion_confidence=0.7,
            coordination_quality=0.9,
            demand_rate=0.8,
        ),
    )
    legacy = kernel.maestro_snapshot()
    shadow = kernel.psi_v2_shadow_snapshot()
    assert legacy["handoffs"][0]["psi"] == pytest.approx(edge.psi)
    assert legacy["workflows"][0]["psi"] == pytest.approx(workflow.psi)
    assert "psi_v2_shadow" not in legacy["handoffs"][0]
    assert "psi_v2_shadow" not in legacy["workflows"][0]
    assert shadow["handoffs"]["a->b"]["observations"] == 1
    assert shadow["workflows"]["wf"]["observations"] == 1


def test_shadow_failure_never_blocks_governance(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ProcessualCGTKernel()
    kernel.register_agent(AgentSpec(agent_id="a", role="worker"))

    def explode(*args, **kwargs):
        raise RuntimeError("shadow failure")

    monkeypatch.setattr(kernel.psi_v2, "advance", explode)
    decision = kernel.observe("a", AgentTelemetry(success_rate=0.9, demand_rate=0.9))
    assert decision.agent_id == "a"
    shadow = kernel.psi_v2_shadow_snapshot()
    assert "a" in shadow["errors"]
    assert "shadow failure" in shadow["errors"]["a"]
