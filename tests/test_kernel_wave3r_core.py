from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processual_kernel.kernel import ProcessualCGTKernel, ProcessualMaestroKernel
from processual_kernel.types import (
    AgentSpec,
    AgentState,
    AgentTelemetry,
    Coefficients,
    HandoffRecord,
    KernelPolicy,
    MaestroAction,
    StepRecord,
    StepState,
    TaskEnvelope,
    TaskResult,
    WorkflowPlan,
    WorkflowState,
    WorkflowStep,
)


class FakeRuntime:
    def __init__(self, results: list[TaskResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[AgentSpec, TaskEnvelope]] = []

    async def run(self, agent: AgentSpec, task: TaskEnvelope) -> TaskResult:
        self.calls.append((agent, task))
        return self.results.pop(0)


class AuditCollector:
    def __init__(self) -> None:
        self.events: list[object] = []

    def write(self, event: object) -> None:
        self.events.append(event)


def make_agent(agent_id: str, capability: str = "write") -> AgentSpec:
    return AgentSpec(agent_id=agent_id, role="worker", capabilities=(capability,))


def make_plan(*steps: WorkflowStep) -> WorkflowPlan:
    return WorkflowPlan(workflow_id="wf-1", goal="ship", steps=tuple(steps), priority=0.8)


def test_register_get_snapshot_and_active_ratio() -> None:
    kernel = ProcessualCGTKernel()
    assert kernel.active_ratio() == 0.0

    first = kernel.register_agent(make_agent("a1"), AgentTelemetry(success_rate=0.9))
    second = kernel.register_agent(make_agent("a2"))
    second.state = AgentState.ARCHIVED
    first.psi = 1.25
    first.previous_psi = 0.5
    first.failure_streak = 2
    first.observations = 3

    assert kernel.get_agent("a1") is first
    assert first.last_coefficients is not None
    assert kernel.active_ratio() == 0.5

    snapshot = kernel.snapshot()
    assert snapshot[0]["agent_id"] == "a1"
    assert snapshot[0]["state"] == "active"
    assert snapshot[0]["psi"] == 1.25
    assert snapshot[0]["previous_psi"] == 0.5
    assert snapshot[0]["failure_streak"] == 2
    assert snapshot[0]["observations"] == 3
    assert snapshot[0]["capabilities"] == ["write"]
    assert snapshot[0]["last_coefficients"] is not None
    assert snapshot[1]["last_coefficients"] is None

    with pytest.raises(ValueError, match="agent already registered: a1"):
        kernel.register_agent(make_agent("a1"))
    with pytest.raises(KeyError, match="unknown agent: missing"):
        kernel.get_agent("missing")


def test_audit_is_optional_and_routes_to_sink() -> None:
    collector = AuditCollector()
    kernel = ProcessualCGTKernel(audit_sink=collector)
    marker = object()
    kernel._audit(marker)
    assert collector.events == [marker]

    ProcessualCGTKernel()._audit(marker)


def test_route_candidates_filters_and_sorts() -> None:
    kernel = ProcessualCGTKernel()
    a1 = kernel.register_agent(make_agent("a1"))
    a2 = kernel.register_agent(make_agent("a2"))
    a3 = kernel.register_agent(make_agent("a3", "read"))
    a4 = kernel.register_agent(make_agent("a4"))
    a1.psi, a1.failure_streak = 0.7, 3
    a2.psi, a2.failure_streak = 0.7, 1
    a3.psi = 9.0
    a4.state = AgentState.ARCHIVED

    task = TaskEnvelope(task_id="t", required_capability="write")
    assert [r.spec.agent_id for r in kernel.route_candidates(task)] == ["a2", "a1"]

    unsorted = ProcessualCGTKernel(policy=KernelPolicy(prefer_high_psi_agents=False))
    unsorted.register_agent(make_agent("x1"))
    unsorted.register_agent(make_agent("x2"))
    assert [r.spec.agent_id for r in unsorted.route_candidates(task)] == ["x1", "x2"]


@pytest.mark.asyncio
async def test_run_task_requires_runtime_and_candidate() -> None:
    task = TaskEnvelope(task_id="t", required_capability="write")
    with pytest.raises(RuntimeError, match="No AgentRuntime configured"):
        await ProcessualCGTKernel().run_task(task)

    runtime = FakeRuntime([])
    with pytest.raises(RuntimeError, match="No active agent can handle capability: write"):
        await ProcessualCGTKernel(runtime=runtime).run_task(task)


@pytest.mark.asyncio
async def test_run_task_success_and_failure_observe_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    ok_runtime = FakeRuntime([TaskResult(task_id="t1", agent_id="a1", ok=True, output="ok", cost=2.0)])
    ok_kernel = ProcessualCGTKernel(runtime=ok_runtime)
    ok_kernel.register_agent(make_agent("a1"))
    observed_ok = Mock()
    monkeypatch.setattr(ok_kernel, "observe", observed_ok)

    result = await ok_kernel.run_task(TaskEnvelope(task_id="t1", required_capability="write", priority=1.4))
    assert result.output == "ok"
    observed_ok.assert_called_once()
    telemetry = observed_ok.call_args.args[1]
    assert telemetry.success_rate == 1.0
    assert telemetry.demand_rate == 1.0
    assert telemetry.business_priority == 1.4
    assert telemetry.resource_cost == 1.0
    assert telemetry.failure_count == 0
    assert telemetry.latency_p95_ms > 0

    fail_runtime = FakeRuntime(
        [TaskResult(task_id="t2", agent_id="a1", ok=False, error="boom", latency_ms=25.0, cost=0.2)]
    )
    fail_kernel = ProcessualCGTKernel(runtime=fail_runtime)
    record = fail_kernel.register_agent(make_agent("a1"))
    record.failure_streak = 4
    observed_fail = Mock()
    monkeypatch.setattr(fail_kernel, "observe", observed_fail)

    result = await fail_kernel.run_task(TaskEnvelope(task_id="t2", required_capability="write", priority=0.4))
    assert result.error == "boom"
    telemetry = observed_fail.call_args.args[1]
    assert telemetry.success_rate == 0.0
    assert telemetry.failure_count == 5
    assert telemetry.latency_p95_ms == 25.0


def test_workflow_creation_lookup_emit_and_ready_steps() -> None:
    collector = AuditCollector()
    kernel = ProcessualMaestroKernel(audit_sink=collector)
    first = WorkflowStep(step_id="s1", capability="write", instruction="first")
    second = WorkflowStep(step_id="s2", capability="write", instruction="second", depends_on=("s1",))
    workflow = kernel.create_workflow(make_plan(first, second))

    assert kernel.get_workflow("wf-1") is workflow
    assert kernel.events[-1].action == MaestroAction.OBSERVE
    assert collector.events[-1] is kernel.events[-1]
    assert [r.step.step_id for r in kernel.ready_steps("wf-1")] == ["s1"]

    workflow.steps["s1"].state = StepState.COMPLETED
    assert [r.step.step_id for r in kernel.ready_steps("wf-1")] == ["s2"]
    workflow.steps["s2"].state = StepState.RUNNING
    assert kernel.ready_steps("wf-1") == []

    event = kernel.emit("wf-1", MaestroAction.PAUSE, "wf-1", "manual")
    assert event.payload == {}
    with pytest.raises(ValueError, match="workflow already exists: wf-1"):
        kernel.create_workflow(make_plan(first))
    with pytest.raises(KeyError, match="unknown workflow: missing"):
        kernel.get_workflow("missing")


def test_assign_agent_preferred_fallback_and_missing() -> None:
    kernel = ProcessualMaestroKernel()
    preferred = kernel.register_agent(make_agent("preferred"))
    fallback = kernel.register_agent(make_agent("fallback"))
    preferred.psi = 0.1
    fallback.psi = 0.9

    step = StepRecord(
        step=WorkflowStep(
            step_id="s1", capability="write", instruction="go", preferred_agent_id="preferred"
        )
    )
    assert kernel.assign_agent(step) is preferred

    preferred.state = AgentState.ARCHIVED
    assert kernel.assign_agent(step) is fallback

    missing = StepRecord(step=WorkflowStep(step_id="s2", capability="missing", instruction="go"))
    with pytest.raises(RuntimeError, match="no active agent can execute step s2 capability=missing"):
        kernel.assign_agent(missing)


def test_dependency_outputs_and_handoff_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ProcessualMaestroKernel()
    first = WorkflowStep(step_id="s1", capability="write", instruction="first")
    second = WorkflowStep(step_id="s2", capability="write", instruction="second", depends_on=("s1",))
    workflow = kernel.create_workflow(make_plan(first, second))
    workflow.steps["s1"].output = {"artifact": 1}
    assert kernel._dependency_outputs(workflow, workflow.steps["s2"]) == {"s1": {"artifact": 1}}

    observe_handoff = Mock()
    monkeypatch.setattr(kernel, "observe_handoff", observe_handoff)
    kernel._observe_step_handoffs(workflow, workflow.steps["s1"])
    assert observe_handoff.call_count == 0

    workflow.steps["s2"].assigned_agent_id = "a2"
    kernel._observe_step_handoffs(workflow, workflow.steps["s2"])
    assert observe_handoff.call_count == 0

    workflow.steps["s1"].assigned_agent_id = "a1"
    workflow.steps["s2"].state = StepState.COMPLETED
    kernel._observe_step_handoffs(workflow, workflow.steps["s2"])
    telemetry = observe_handoff.call_args.args[2]
    assert telemetry.artifact_quality == 0.85
    assert telemetry.rework_rate == 0.05

    workflow.steps["s2"].state = StepState.FAILED
    kernel._observe_step_handoffs(workflow, workflow.steps["s2"])
    telemetry = observe_handoff.call_args.args[2]
    assert telemetry.artifact_quality == 0.25
    assert telemetry.rework_rate == 0.75


@pytest.mark.asyncio
async def test_run_step_success_retry_and_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = make_agent("a1")
    plan = make_plan(WorkflowStep(step_id="s1", capability="write", instruction="do", max_retries=2))

    success_runtime = FakeRuntime([TaskResult(task_id="x", agent_id="a1", ok=True, output="done", cost=0.3)])
    success_kernel = ProcessualMaestroKernel(runtime=success_runtime)
    success_kernel.register_agent(agent)
    workflow = success_kernel.create_workflow(plan)
    monkeypatch.setattr(success_kernel, "observe", Mock())
    await success_kernel._run_step(workflow, workflow.steps["s1"])
    record = workflow.steps["s1"]
    assert record.state == StepState.COMPLETED
    assert record.output == "done"
    assert record.attempts == 1
    assert success_runtime.calls[0][1].payload["dependencies"] == {}

    retry_runtime = FakeRuntime([TaskResult(task_id="x", agent_id="a1", ok=False, error="fail")])
    retry_kernel = ProcessualMaestroKernel(runtime=retry_runtime)
    retry_kernel.register_agent(agent)
    retry_workflow = retry_kernel.create_workflow(plan)
    monkeypatch.setattr(retry_kernel, "observe", Mock())
    await retry_kernel._run_step(retry_workflow, retry_workflow.steps["s1"])
    assert retry_workflow.steps["s1"].state == StepState.PENDING
    assert retry_kernel.events[-1].action == MaestroAction.RETRY

    exhausted_plan = make_plan(WorkflowStep(step_id="s1", capability="write", instruction="do", max_retries=1))
    exhausted_runtime = FakeRuntime([TaskResult(task_id="x", agent_id="a1", ok=False, error="fail")])
    exhausted_kernel = ProcessualMaestroKernel(runtime=exhausted_runtime)
    exhausted_kernel.register_agent(agent)
    exhausted_workflow = exhausted_kernel.create_workflow(exhausted_plan)
    monkeypatch.setattr(exhausted_kernel, "observe", Mock())
    await exhausted_kernel._run_step(exhausted_workflow, exhausted_workflow.steps["s1"])
    assert exhausted_workflow.steps["s1"].state == StepState.FAILED
    assert exhausted_kernel.events[-1].action == MaestroAction.REROUTE


@pytest.mark.asyncio
async def test_run_workflow_requires_runtime_and_processes_ready_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    step = WorkflowStep(step_id="s1", capability="write", instruction="do")
    no_runtime = ProcessualMaestroKernel()
    no_runtime.create_workflow(make_plan(step))
    with pytest.raises(RuntimeError, match="No AgentRuntime configured"):
        await no_runtime.run_workflow("wf-1")

    runtime = FakeRuntime([])
    kernel = ProcessualMaestroKernel(runtime=runtime)
    workflow = kernel.create_workflow(make_plan(step))
    run_step = Mock()

    async def fake_run_step(_workflow: object, step_record: StepRecord) -> None:
        run_step(step_record)
        step_record.state = StepState.COMPLETED

    monkeypatch.setattr(kernel, "_run_step", fake_run_step)
    monkeypatch.setattr(kernel, "_observe_step_handoffs", Mock())
    observe_workflow = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr(kernel, "_observe_workflow_from_steps", observe_workflow)

    result = await kernel.run_workflow("wf-1")
    assert result is workflow
    assert workflow.state == WorkflowState.RUNNING
    assert run_step.call_count == 1
    assert observe_workflow.call_count == 2


def test_observe_workflow_from_steps_builds_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ProcessualMaestroKernel()
    steps = (
        WorkflowStep(step_id="s1", capability="write", instruction="1"),
        WorkflowStep(step_id="s2", capability="write", instruction="2"),
        WorkflowStep(step_id="s3", capability="write", instruction="3"),
    )
    workflow = kernel.create_workflow(make_plan(*steps))
    workflow.steps["s1"].state = StepState.COMPLETED
    workflow.steps["s2"].state = StepState.FAILED
    workflow.steps["s3"].state = StepState.RUNNING
    decision = object()
    observe = Mock(return_value=decision)
    monkeypatch.setattr(kernel, "observe_workflow", observe)

    assert kernel._observe_workflow_from_steps(workflow) is decision
    telemetry = observe.call_args.args[1]
    assert telemetry.progress_rate == pytest.approx(1 / 3)
    assert telemetry.blocking_rate == pytest.approx(1 / 3)
    assert telemetry.completion_confidence == pytest.approx(2 / 9)
    assert telemetry.goal_alignment == 0.55
    assert telemetry.coordination_quality == 0.45
    assert telemetry.latency_pressure == pytest.approx(0.15)
    assert telemetry.custom == {"business_priority": 0.8}


def test_intervene_updates_known_states_and_emits() -> None:
    kernel = ProcessualMaestroKernel()
    step = WorkflowStep(step_id="s1", capability="write", instruction="do")
    workflow = kernel.create_workflow(make_plan(step))

    cases = [
        (MaestroAction.PAUSE, WorkflowState.PAUSED),
        (MaestroAction.ESCALATE, WorkflowState.ESCALATED),
        (MaestroAction.FINALIZE, WorkflowState.COMPLETED),
        (MaestroAction.REROUTE, WorkflowState.DEGRADED),
    ]
    for action, expected in cases:
        event = kernel.intervene("wf-1", action, "wf-1", "reason", {"x": 1})
        assert workflow.state == expected
        assert event.action == action
        assert event.payload == {"x": 1}

    previous = workflow.state
    event = kernel.intervene("wf-1", MaestroAction.OBSERVE, "wf-1", "noop")
    assert workflow.state == previous
    assert event.payload == {}


def test_maestro_snapshot_includes_agents_handoffs_workflows_and_events() -> None:
    kernel = ProcessualMaestroKernel()
    agent = kernel.register_agent(make_agent("a1"))
    agent.last_coefficients = Coefficients(T=0.1, N=0.2, C=0.3, M=0.4)
    handoff = HandoffRecord(source_agent_id="a1", target_agent_id="a2")
    handoff.psi = 0.6
    handoff.observations = 2
    handoff.last_coefficients = Coefficients(T=0.4, N=0.5, C=0.2, M=0.1)
    kernel.handoffs[handoff.edge_id] = handoff
    step = WorkflowStep(step_id="s1", capability="write", instruction="do")
    workflow = kernel.create_workflow(make_plan(step))
    workflow.steps["s1"].assigned_agent_id = "a1"
    workflow.steps["s1"].attempts = 2
    workflow.steps["s1"].error = "old"

    snapshot = kernel.maestro_snapshot()
    assert snapshot["agents"][0]["agent_id"] == "a1"
    assert snapshot["handoffs"][0]["edge_id"] == "a1->a2"
    assert snapshot["handoffs"][0]["last_coefficients"]["T"] == 0.4
    assert snapshot["workflows"][0]["workflow_id"] == "wf-1"
    assert snapshot["workflows"][0]["steps"]["s1"] == {
        "state": "pending",
        "assigned_agent_id": "a1",
        "attempts": 2,
        "error": "old",
    }
    assert snapshot["events"][0]["action"] == MaestroAction.OBSERVE
