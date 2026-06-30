import asyncio
import json
from dataclasses import asdict

import pytest

from processual_kernel.audit import (
    AuditEventType,
    JsonlAuditSink,
    normalize_audit_event,
)
from processual_kernel.continuity import (
    ContinuityEngine,
    MetricCoefficientMapper,
    clamp,
)
from processual_kernel.kernel import ProcessualCGTKernel, ProcessualMaestroKernel
from processual_kernel.types import (
    AgentCriticality,
    AgentSpec,
    AgentState,
    AgentTelemetry,
    Coefficients,
    EdgeDecision,
    GovernanceDecision,
    HandoffTelemetry,
    KernelPolicy,
    MaestroAction,
    TaskEnvelope,
    TaskResult,
    WorkflowDecision,
    WorkflowPlan,
    WorkflowState,
    WorkflowStep,
    WorkflowTelemetry,
)


class _AuditCollector:
    def __init__(self):
        self.events = []

    def write(self, event):
        self.events.append(event)


class _FakeCGT:
    def evaluate_transition(self, **kwargs):
        return {"fake_report": True, **kwargs}

    def report_to_dict(self, report):
        return {
            "fake_report": True,
            "entity_id": report.get("entity_id"),
        }


class _FakeGovernor:
    def __init__(self):
        self.agent_decisions = []
        self.edge_decisions = []
        self.workflow_decisions = []

    def decide(self, record, coeff, dpsi, report, cgt_dict):
        decision = GovernanceDecision(
            agent_id=record.spec.agent_id,
            previous_state=record.state,
            new_state=AgentState.ACTIVE,
            psi=record.psi,
            dpsi=dpsi,
            coefficients=coeff,
            reason="fake agent governance",
            cgt=cgt_dict,
            confidence=0.9,
            policy_version="test-policy",
        )
        self.agent_decisions.append(decision)
        return decision

    def decide_edge(self, record, coeff, dpsi, report, cgt_dict):
        decision = EdgeDecision(
            edge_id=record.edge_id,
            source_agent_id=record.source_agent_id,
            target_agent_id=record.target_agent_id,
            previous_state=record.state,
            new_state=AgentState.ACTIVE,
            psi=record.psi,
            dpsi=dpsi,
            coefficients=coeff,
            reason="fake edge governance",
            cgt=cgt_dict,
            action=MaestroAction.HANDOFF,
            confidence=0.8,
            policy_version="test-policy",
        )
        self.edge_decisions.append(decision)
        return decision

    def decide_workflow(self, record, coeff, dpsi, report, cgt_dict):
        completed = sum(
            1 for step in record.steps.values() if step.state.value == "completed"
        )
        new_state = (
            WorkflowState.COMPLETED
            if completed == len(record.steps) and record.steps
            else WorkflowState.RUNNING
        )
        action = (
            MaestroAction.FINALIZE
            if new_state == WorkflowState.COMPLETED
            else MaestroAction.DELEGATE
        )
        decision = WorkflowDecision(
            workflow_id=record.plan.workflow_id,
            previous_state=record.state,
            new_state=new_state,
            psi=record.psi,
            dpsi=dpsi,
            coefficients=coeff,
            reason="fake workflow governance",
            action=action,
            cgt=cgt_dict,
            confidence=0.85,
            policy_version="test-policy",
        )
        self.workflow_decisions.append(decision)
        return decision


class _FakeRuntime:
    def __init__(self):
        self.calls = []

    async def run(self, agent, task):
        self.calls.append({"agent": agent, "task": task})
        return TaskResult(
            task_id=task.task_id,
            agent_id=agent.agent_id,
            ok=True,
            output={
                "agent_id": agent.agent_id,
                "task_id": task.task_id,
                "payload": task.payload,
            },
            latency_ms=12.5,
            cost=0.1,
        )


def _kernel_with_fakes(runtime=None, audit_sink=None):
    kernel = ProcessualMaestroKernel(runtime=runtime, audit_sink=audit_sink)
    kernel.cgt = _FakeCGT()
    kernel.governor = _FakeGovernor()
    return kernel


def test_continuity_mapper_clamp_and_normalize_are_stable():
    assert clamp(float("nan")) == 0.0
    assert clamp(-1.0) == 0.0
    assert clamp(2.0) == 1.0

    mapper = MetricCoefficientMapper()
    coeff = mapper.from_agent_telemetry(
        AgentTelemetry(
            success_rate=1.0,
            cooperation_success=0.8,
            useful_handoff_rate=0.6,
            demand_rate=0.7,
            business_priority=0.9,
            resource_cost=0.2,
            failure_count=1,
            latency_p95_ms=250,
        )
    )

    assert isinstance(coeff, Coefficients)
    assert 0.0 <= coeff.T <= 1.0
    assert 0.0 <= coeff.N <= 1.0
    assert 0.0 <= coeff.C <= 1.0
    assert 0.0 <= coeff.M <= 1.0

    engine = ContinuityEngine(dt=2.0)
    delta = engine.delta(coeff)
    new_psi, dpsi = engine.step(0.25, coeff)

    assert dpsi == delta
    assert new_psi == 0.25 + delta
    assert 0.0 <= ContinuityEngine.normalize_psi(new_psi) <= 1.0

    with pytest.raises(ValueError):
        ContinuityEngine(dt=0)


def test_kernel_registers_routes_and_observes_agent_with_audit():
    audit = _AuditCollector()
    kernel = _kernel_with_fakes(audit_sink=audit)

    writer = kernel.register_agent(
        AgentSpec(
            agent_id="writer",
            role="Writer",
            capabilities=("draft", "review"),
            criticality=AgentCriticality.HIGH,
        )
    )
    reviewer = kernel.register_agent(
        AgentSpec(
            agent_id="reviewer",
            role="Reviewer",
            capabilities=("review",),
        )
    )

    writer.psi = 0.2
    reviewer.psi = 0.8

    with pytest.raises(ValueError):
        kernel.register_agent(
            AgentSpec(agent_id="writer", role="Duplicate", capabilities=("draft",))
        )

    with pytest.raises(KeyError):
        kernel.get_agent("missing")

    candidates = kernel.route_candidates(
        TaskEnvelope(task_id="task-review", required_capability="review")
    )

    assert [candidate.spec.agent_id for candidate in candidates] == [
        "reviewer",
        "writer",
    ]
    assert kernel.active_ratio() == 1.0

    decision = kernel.observe(
        "writer",
        AgentTelemetry(
            success_rate=1.0,
            cooperation_success=0.9,
            useful_handoff_rate=0.9,
            demand_rate=0.8,
            business_priority=0.8,
            failure_count=0,
        ),
    )

    assert decision.agent_id == "writer"
    assert decision.reason == "fake agent governance"

    updated = kernel.get_agent("writer")
    assert updated.observations == 1
    assert updated.last_coefficients is not None
    assert audit.events[-1] == decision

    snapshot = kernel.snapshot()
    assert {row["agent_id"] for row in snapshot} == {"writer", "reviewer"}
    assert snapshot[0]["state"] in {
        AgentState.ACTIVE.value,
        AgentState.TRANSITIONAL.value,
        AgentState.ARCHIVED.value,
        AgentState.QUARANTINED.value,
    }


def test_run_task_requires_runtime_and_executes_best_candidate():
    kernel_without_runtime = _kernel_with_fakes()
    kernel_without_runtime.register_agent(
        AgentSpec(agent_id="agent-1", role="Worker", capabilities=("draft",))
    )

    with pytest.raises(RuntimeError, match="No AgentRuntime configured"):
        asyncio.run(
            kernel_without_runtime.run_task(
                TaskEnvelope(task_id="task-1", required_capability="draft")
            )
        )

    runtime = _FakeRuntime()
    kernel = _kernel_with_fakes(runtime=runtime)
    low = kernel.register_agent(
        AgentSpec(agent_id="low", role="Low", capabilities=("draft",))
    )
    high = kernel.register_agent(
        AgentSpec(agent_id="high", role="High", capabilities=("draft",))
    )

    low.psi = 0.1
    high.psi = 0.9

    result = asyncio.run(
        kernel.run_task(
            TaskEnvelope(
                task_id="task-2",
                required_capability="draft",
                payload={"instruction": "Write"},
                priority=0.7,
            )
        )
    )

    assert result.ok is True
    assert result.agent_id == "high"
    assert runtime.calls[0]["agent"].agent_id == "high"
    assert kernel.get_agent("high").observations == 1


def test_workflow_creation_ready_steps_intervention_and_snapshot():
    audit = _AuditCollector()
    kernel = _kernel_with_fakes(audit_sink=audit)

    plan = WorkflowPlan(
        workflow_id="wf-1",
        goal="Prepare report",
        steps=(
            WorkflowStep(
                step_id="draft",
                capability="draft",
                instruction="Draft the report",
            ),
            WorkflowStep(
                step_id="review",
                capability="review",
                instruction="Review the report",
                depends_on=("draft",),
            ),
        ),
        priority=0.75,
    )

    workflow = kernel.create_workflow(plan)

    assert workflow.plan.workflow_id == "wf-1"
    assert set(workflow.steps) == {"draft", "review"}
    assert kernel.events[-1].action == MaestroAction.OBSERVE
    assert audit.events[-1].subject == "wf-1"

    with pytest.raises(ValueError):
        kernel.create_workflow(plan)

    ready = kernel.ready_steps("wf-1")
    assert [step.step.step_id for step in ready] == ["draft"]

    workflow.steps["draft"].state = workflow.steps["draft"].state.COMPLETED
    ready_after_draft = kernel.ready_steps("wf-1")
    assert [step.step.step_id for step in ready_after_draft] == ["review"]

    pause_event = kernel.intervene(
        "wf-1",
        MaestroAction.PAUSE,
        "wf-1",
        "manual pause",
        {"operator": "test"},
    )

    assert pause_event.action == MaestroAction.PAUSE
    assert kernel.get_workflow("wf-1").state == WorkflowState.PAUSED

    snapshot = kernel.maestro_snapshot()
    assert snapshot["workflows"][0]["workflow_id"] == "wf-1"
    assert snapshot["workflows"][0]["steps"]["draft"]["state"] == "completed"
    assert snapshot["events"]


def test_maestro_runs_workflow_and_observes_handoffs():
    runtime = _FakeRuntime()
    kernel = _kernel_with_fakes(runtime=runtime)

    kernel.register_agent(
        AgentSpec(agent_id="writer", role="Writer", capabilities=("draft",))
    )
    kernel.register_agent(
        AgentSpec(agent_id="reviewer", role="Reviewer", capabilities=("review",))
    )

    plan = WorkflowPlan(
        workflow_id="wf-run",
        goal="Run report workflow",
        steps=(
            WorkflowStep(
                step_id="draft",
                capability="draft",
                instruction="Draft the report",
                preferred_agent_id="writer",
            ),
            WorkflowStep(
                step_id="review",
                capability="review",
                instruction="Review the report",
                depends_on=("draft",),
                preferred_agent_id="reviewer",
            ),
        ),
        priority=0.6,
    )
    workflow = kernel.create_workflow(plan)

    result = asyncio.run(kernel.run_workflow("wf-run"))

    assert result is workflow
    assert result.steps["draft"].state.value == "completed"
    assert result.steps["review"].state.value == "completed"
    assert result.steps["draft"].assigned_agent_id == "writer"
    assert result.steps["review"].assigned_agent_id == "reviewer"
    assert len(runtime.calls) == 2

    assert "writer->reviewer" in kernel.handoffs
    edge = kernel.handoffs["writer->reviewer"]
    assert edge.observations == 1
    assert kernel.governor.edge_decisions

    assert kernel.governor.workflow_decisions
    assert kernel.get_workflow("wf-run").state == WorkflowState.COMPLETED


def test_audit_normalization_and_jsonl_sink(tmp_path):
    decision = GovernanceDecision(
        agent_id="agent-audit",
        previous_state=AgentState.ACTIVE,
        new_state=AgentState.TRANSITIONAL,
        psi=0.1,
        dpsi=-0.2,
        coefficients=Coefficients(T=0.1, N=0.2, C=0.3, M=0.4),
        reason="audit test",
        cgt={"rank": "distorted"},
        policy_version="policy-test",
    )

    normalized = normalize_audit_event(decision)

    assert normalized.event_type == AuditEventType.GOVERNANCE_DECISION
    assert normalized.subject_id == "agent-audit"
    assert normalized.policy_version == "policy-test"
    assert normalized.decision_id == decision.decision_id

    unknown = normalize_audit_event(
        {
            "event_type": "not-real",
            "subject_id": "subject-x",
            "payload": "value",
        }
    )

    assert unknown.event_type == AuditEventType.UNKNOWN
    assert unknown.subject_id == "subject-x"

    path = tmp_path / "audit" / "events.jsonl"
    sink = JsonlAuditSink(path)
    sink.write(decision)
    sink.write({"event_type": "metrics_snapshot", "subject_id": "metrics"})

    lines = path.read_text("utf-8").splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["event_type"] == "governance_decision"
    assert first["subject_id"] == "agent-audit"
    assert second["event_type"] == "metrics_snapshot"
    assert second["subject_id"] == "metrics"

    # Ensure JSON serialization stayed dataclass/enum-safe.
    assert asdict(decision)["previous_state"] == AgentState.ACTIVE