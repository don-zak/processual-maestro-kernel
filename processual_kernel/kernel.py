from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from .cgt_bridge import CGTBridge
from .continuity import ContinuityEngine, MetricCoefficientMapper
from .governor import LifecycleGovernor
from .types import (
    AgentRecord,
    AgentRuntime,
    AgentSpec,
    AgentState,
    AgentTelemetry,
    AuditSink,
    EdgeDecision,
    GovernanceDecision,
    HandoffRecord,
    HandoffTelemetry,
    KernelPolicy,
    MaestroAction,
    MaestroEvent,
    StepRecord,
    StepState,
    TaskEnvelope,
    TaskResult,
    WorkflowDecision,
    WorkflowPlan,
    WorkflowRecord,
    WorkflowState,
    WorkflowTelemetry,
)


class ProcessualCGTKernel:
    """Backward-compatible single-agent governance kernel."""

    def __init__(
        self,
        runtime: AgentRuntime | None = None,
        policy: KernelPolicy | None = None,
        audit_sink: AuditSink | None = None,
    ):
        self.policy = policy or KernelPolicy()
        self.runtime = runtime
        self.registry: dict[str, AgentRecord] = {}
        self.mapper = MetricCoefficientMapper()
        self.continuity = ContinuityEngine(dt=self.policy.dt)
        self.cgt = CGTBridge()
        self.governor = LifecycleGovernor(self.policy)
        self.audit_sink = audit_sink

    def _audit(self, event: Any) -> None:
        if self.audit_sink is not None:
            self.audit_sink.write(event)

    def register_agent(self, spec: AgentSpec, initial_telemetry: AgentTelemetry | None = None) -> AgentRecord:
        if spec.agent_id in self.registry:
            raise ValueError(f"agent already registered: {spec.agent_id}")
        record = AgentRecord(spec=spec)
        if initial_telemetry is not None:
            record.last_coefficients = self.mapper.from_agent_telemetry(initial_telemetry)
        self.registry[spec.agent_id] = record
        return record

    def get_agent(self, agent_id: str) -> AgentRecord:
        try:
            return self.registry[agent_id]
        except KeyError:
            raise KeyError(f"unknown agent: {agent_id}") from None

    def observe(self, agent_id: str, telemetry: AgentTelemetry) -> GovernanceDecision:
        record = self.get_agent(agent_id)
        previous_coeff = record.last_coefficients or self.mapper.from_agent_telemetry(AgentTelemetry())
        coeff = self.mapper.from_agent_telemetry(telemetry)

        record.previous_psi = record.psi
        new_psi, dpsi = self.continuity.step(record.psi, coeff)
        record.psi = new_psi
        record.failure_streak = telemetry.failure_count
        record.last_coefficients = coeff
        record.last_updated_at = time.time()
        record.observations += 1

        report = self.cgt.evaluate_transition(
            entity_id=agent_id,
            previous_coeff=previous_coeff,
            current_coeff=coeff,
            previous_psi=record.previous_psi,
            current_psi=record.psi,
            dpsi=dpsi,
            fatigue_counter=record.failure_streak,
        )
        cgt_dict = self.cgt.report_to_dict(report)
        decision = self.governor.decide(record, coeff, dpsi, report, cgt_dict)
        record.state = decision.new_state
        self._audit(decision)
        return decision

    def route_candidates(self, task: TaskEnvelope) -> list[AgentRecord]:
        candidates = [
            r
            for r in self.registry.values()
            if r.state == AgentState.ACTIVE and task.required_capability in r.spec.capabilities
        ]
        if self.policy.prefer_high_psi_agents:
            return sorted(candidates, key=lambda r: (r.psi, -r.failure_streak), reverse=True)
        return candidates

    async def run_task(self, task: TaskEnvelope) -> TaskResult:
        if self.runtime is None:
            raise RuntimeError("No AgentRuntime configured")
        candidates = self.route_candidates(task)
        if not candidates:
            raise RuntimeError(f"No active agent can handle capability: {task.required_capability}")
        chosen = candidates[0].spec
        started = time.perf_counter()
        result = await self.runtime.run(chosen, task)
        latency_ms = result.latency_ms or (time.perf_counter() - started) * 1000
        failure_count = 0 if result.ok else self.get_agent(chosen.agent_id).failure_streak + 1
        telemetry = AgentTelemetry(
            success_rate=1.0 if result.ok else 0.0,
            cooperation_success=0.6,
            useful_handoff_rate=0.6,
            demand_rate=min(1.0, task.priority),
            business_priority=task.priority,
            resource_cost=min(1.0, result.cost),
            failure_count=failure_count,
            latency_p95_ms=latency_ms,
        )
        self.observe(chosen.agent_id, telemetry)
        return result

    def snapshot(self) -> list[dict]:
        return [self._agent_snapshot(r) for r in self.registry.values()]

    def _agent_snapshot(self, r: AgentRecord) -> dict[str, Any]:
        return {
            "agent_id": r.spec.agent_id,
            "role": r.spec.role,
            "state": r.state.value,
            "psi": r.psi,
            "previous_psi": r.previous_psi,
            "failure_streak": r.failure_streak,
            "observations": r.observations,
            "criticality": r.spec.criticality.value,
            "capabilities": list(r.spec.capabilities),
            "last_coefficients": asdict(r.last_coefficients) if r.last_coefficients else None,
        }

    def active_ratio(self) -> float:
        if not self.registry:
            return 0.0
        return sum(1 for r in self.registry.values() if r.state == AgentState.ACTIVE) / len(self.registry)


class ProcessualMaestroKernel(ProcessualCGTKernel):
    """Workflow maestro for self-healing multi-agent orchestration.

    The maestro does not replace the LLM/agent runtime. It conducts the workflow:
    chooses agents, observes handoffs, evaluates workflow vitality, and intervenes.
    """

    def __init__(
        self,
        runtime: AgentRuntime | None = None,
        policy: KernelPolicy | None = None,
        audit_sink: AuditSink | None = None,
    ):
        super().__init__(runtime=runtime, policy=policy, audit_sink=audit_sink)
        self.handoffs: dict[str, HandoffRecord] = {}
        self.workflows: dict[str, WorkflowRecord] = {}
        self.events: list[MaestroEvent] = []

    def create_workflow(self, plan: WorkflowPlan) -> WorkflowRecord:
        if plan.workflow_id in self.workflows:
            raise ValueError(f"workflow already exists: {plan.workflow_id}")
        steps = {s.step_id: StepRecord(step=s) for s in plan.steps}
        record = WorkflowRecord(plan=plan, steps=steps)
        self.workflows[plan.workflow_id] = record
        self.emit(None, MaestroAction.OBSERVE, plan.workflow_id, "workflow created", {"goal": plan.goal})
        return record

    def get_workflow(self, workflow_id: str) -> WorkflowRecord:
        try:
            return self.workflows[workflow_id]
        except KeyError:
            raise KeyError(f"unknown workflow: {workflow_id}") from None

    def emit(
        self,
        workflow_id: str | None,
        action: MaestroAction,
        subject: str,
        reason: str,
        payload: dict[str, Any] | None = None,
    ) -> MaestroEvent:
        event = MaestroEvent(
            workflow_id=workflow_id, action=action, subject=subject, reason=reason, payload=payload or {}
        )
        self.events.append(event)
        self._audit(event)
        return event

    def observe_handoff(self, source_agent_id: str, target_agent_id: str, telemetry: HandoffTelemetry) -> EdgeDecision:
        edge_id = f"{source_agent_id}->{target_agent_id}"
        record = self.handoffs.get(edge_id)
        if record is None:
            record = HandoffRecord(source_agent_id=source_agent_id, target_agent_id=target_agent_id)
            self.handoffs[edge_id] = record

        previous_coeff = record.last_coefficients or self.mapper.from_handoff_telemetry(HandoffTelemetry())
        coeff = self.mapper.from_handoff_telemetry(telemetry)
        record.previous_psi = record.psi
        record.psi, dpsi = self.continuity.step(record.psi, coeff)
        record.last_coefficients = coeff
        record.observations += 1
        record.last_updated_at = time.time()

        report = self.cgt.evaluate_transition(
            entity_id=edge_id,
            previous_coeff=previous_coeff,
            current_coeff=coeff,
            previous_psi=record.previous_psi,
            current_psi=record.psi,
            dpsi=dpsi,
            fatigue_counter=int(max(0.0, telemetry.rework_rate) * 10),
        )
        cgt_dict = self.cgt.report_to_dict(report)
        decision = self.governor.decide_edge(record, coeff, dpsi, report, cgt_dict)
        record.state = decision.new_state
        self._audit(decision)
        if decision.action in (MaestroAction.REROUTE, MaestroAction.QUARANTINE):
            self.emit(None, decision.action, edge_id, decision.reason, {"edge_psi": decision.psi})
        return decision

    def observe_workflow(self, workflow_id: str, telemetry: WorkflowTelemetry) -> WorkflowDecision:
        record = self.get_workflow(workflow_id)
        previous_coeff = record.last_coefficients or self.mapper.from_workflow_telemetry(WorkflowTelemetry())
        coeff = self.mapper.from_workflow_telemetry(telemetry)
        record.previous_psi = record.psi
        record.psi, dpsi = self.continuity.step(record.psi, coeff)
        record.last_coefficients = coeff
        record.updated_at = time.time()

        fatigue_counter = sum(1 for s in record.steps.values() if s.state == StepState.FAILED)
        report = self.cgt.evaluate_transition(
            entity_id=workflow_id,
            previous_coeff=previous_coeff,
            current_coeff=coeff,
            previous_psi=record.previous_psi,
            current_psi=record.psi,
            dpsi=dpsi,
            fatigue_counter=fatigue_counter,
        )
        cgt_dict = self.cgt.report_to_dict(report)
        decision = self.governor.decide_workflow(record, coeff, dpsi, report, cgt_dict)
        record.state = decision.new_state
        self._audit(decision)
        self.emit(workflow_id, decision.action, workflow_id, decision.reason, {"workflow_psi": decision.psi})
        return decision

    def ready_steps(self, workflow_id: str) -> list[StepRecord]:
        workflow = self.get_workflow(workflow_id)
        ready: list[StepRecord] = []
        for record in workflow.steps.values():
            if record.state != StepState.PENDING:
                continue
            if all(workflow.steps[d].state == StepState.COMPLETED for d in record.step.depends_on):
                ready.append(record)
        return ready

    def assign_agent(self, step: StepRecord) -> AgentRecord:
        if step.step.preferred_agent_id:
            preferred = self.get_agent(step.step.preferred_agent_id)
            if preferred.state == AgentState.ACTIVE and step.step.capability in preferred.spec.capabilities:
                return preferred
        candidates = self.route_candidates(
            TaskEnvelope(
                task_id=step.step.step_id,
                required_capability=step.step.capability,
                payload={"instruction": step.step.instruction, "metadata": step.step.metadata},
            )
        )
        if not candidates:
            raise RuntimeError(
                f"no active agent can execute step {step.step.step_id} capability={step.step.capability}"
            )
        return candidates[0]

    async def run_workflow(self, workflow_id: str) -> WorkflowRecord:
        if self.runtime is None:
            raise RuntimeError("No AgentRuntime configured")
        workflow = self.get_workflow(workflow_id)
        workflow.state = WorkflowState.RUNNING
        self.emit(workflow_id, MaestroAction.DELEGATE, workflow_id, "workflow started")

        while True:
            ready = self.ready_steps(workflow_id)
            if not ready:
                break
            for step_record in ready:
                await self._run_step(workflow, step_record)
                self._observe_step_handoffs(workflow, step_record)
                self._observe_workflow_from_steps(workflow)
                if workflow.state in (WorkflowState.ESCALATED, WorkflowState.FAILED):
                    return workflow

        self._observe_workflow_from_steps(workflow)
        return workflow

    async def _run_step(self, workflow: WorkflowRecord, step_record: StepRecord) -> None:
        agent = self.assign_agent(step_record)
        step_record.assigned_agent_id = agent.spec.agent_id
        step_record.state = StepState.RUNNING
        step_record.started_at = time.time()
        step_record.attempts += 1
        self.emit(
            workflow.plan.workflow_id,
            MaestroAction.DELEGATE,
            step_record.step.step_id,
            f"assigned to {agent.spec.agent_id}",
        )

        task = TaskEnvelope(
            task_id=f"{workflow.plan.workflow_id}:{step_record.step.step_id}:{step_record.attempts}",
            required_capability=step_record.step.capability,
            payload={
                "workflow_id": workflow.plan.workflow_id,
                "goal": workflow.plan.goal,
                "instruction": step_record.step.instruction,
                "dependencies": self._dependency_outputs(workflow, step_record),
                "metadata": step_record.step.metadata,
            },
            priority=workflow.plan.priority,
        )
        started = time.perf_counter()
        result = await self.runtime.run(agent.spec, task)
        latency_ms = result.latency_ms or (time.perf_counter() - started) * 1000
        step_record.finished_at = time.time()
        step_record.output = result.output
        step_record.error = result.error
        step_record.state = StepState.COMPLETED if result.ok else StepState.FAILED

        previous_failure_streak = self.get_agent(agent.spec.agent_id).failure_streak
        failure_count = 0 if result.ok else previous_failure_streak + 1
        self.observe(
            agent.spec.agent_id,
            AgentTelemetry(
                success_rate=1.0 if result.ok else 0.0,
                cooperation_success=0.65 if result.ok else 0.25,
                useful_handoff_rate=0.65 if result.ok else 0.20,
                demand_rate=min(1.0, workflow.plan.priority),
                business_priority=workflow.plan.priority,
                resource_cost=min(1.0, result.cost),
                failure_count=failure_count,
                latency_p95_ms=latency_ms,
            ),
        )

        if not result.ok and step_record.attempts < min(step_record.step.max_retries, self.policy.max_step_attempts):
            step_record.state = StepState.PENDING
            self.emit(
                workflow.plan.workflow_id, MaestroAction.RETRY, step_record.step.step_id, "step failed; retry scheduled"
            )
        elif not result.ok:
            self.emit(
                workflow.plan.workflow_id,
                MaestroAction.REROUTE,
                step_record.step.step_id,
                "step failed; retries exhausted",
            )

    def _dependency_outputs(self, workflow: WorkflowRecord, step_record: StepRecord) -> dict[str, Any]:
        return {dep: workflow.steps[dep].output for dep in step_record.step.depends_on}

    def _observe_step_handoffs(self, workflow: WorkflowRecord, step_record: StepRecord) -> None:
        if not step_record.step.depends_on or not step_record.assigned_agent_id:
            return
        for dep_id in step_record.step.depends_on:
            dep = workflow.steps[dep_id]
            if not dep.assigned_agent_id:
                continue
            ok = step_record.state == StepState.COMPLETED
            self.observe_handoff(
                dep.assigned_agent_id,
                step_record.assigned_agent_id,
                HandoffTelemetry(
                    artifact_quality=0.85 if ok else 0.25,
                    context_preservation=0.80 if ok else 0.30,
                    acceptance_rate=0.90 if ok else 0.20,
                    rework_rate=0.05 if ok else 0.75,
                    ambiguity=0.10 if ok else 0.70,
                    demand_rate=workflow.plan.priority,
                ),
            )

    def _observe_workflow_from_steps(self, workflow: WorkflowRecord) -> WorkflowDecision:
        total = max(1, len(workflow.steps))
        completed = sum(1 for s in workflow.steps.values() if s.state == StepState.COMPLETED)
        failed = sum(1 for s in workflow.steps.values() if s.state == StepState.FAILED)
        running = sum(1 for s in workflow.steps.values() if s.state == StepState.RUNNING)
        progress = completed / total
        blocking = failed / total
        confidence = progress * (1.0 - blocking)
        telemetry = WorkflowTelemetry(
            goal_alignment=0.9 if failed == 0 else 0.55,
            progress_rate=progress,
            completion_confidence=confidence,
            coordination_quality=0.85 if failed == 0 else 0.45,
            blocking_rate=blocking,
            rework_rate=blocking,
            cost_pressure=0.10 + 0.20 * failed,
            latency_pressure=0.05 + 0.10 * running,
            risk_pressure=0.10 * failed,
            demand_rate=workflow.plan.priority,
            custom={"business_priority": workflow.plan.priority},
        )
        return self.observe_workflow(workflow.plan.workflow_id, telemetry)

    def intervene(
        self, workflow_id: str, action: MaestroAction, subject: str, reason: str, payload: dict[str, Any] | None = None
    ) -> MaestroEvent:
        workflow = self.get_workflow(workflow_id)
        if action == MaestroAction.PAUSE:
            workflow.state = WorkflowState.PAUSED
        elif action == MaestroAction.ESCALATE:
            workflow.state = WorkflowState.ESCALATED
        elif action == MaestroAction.FINALIZE:
            workflow.state = WorkflowState.COMPLETED
        elif action == MaestroAction.REROUTE:
            workflow.state = WorkflowState.DEGRADED
        workflow.updated_at = time.time()
        return self.emit(workflow_id, action, subject, reason, payload or {})

    def maestro_snapshot(self) -> dict[str, Any]:
        return {
            "agents": self.snapshot(),
            "handoffs": [
                {
                    "edge_id": h.edge_id,
                    "source": h.source_agent_id,
                    "target": h.target_agent_id,
                    "state": h.state.value,
                    "psi": h.psi,
                    "observations": h.observations,
                    "last_coefficients": asdict(h.last_coefficients) if h.last_coefficients else None,
                }
                for h in self.handoffs.values()
            ],
            "workflows": [
                {
                    "workflow_id": w.plan.workflow_id,
                    "goal": w.plan.goal,
                    "state": w.state.value,
                    "psi": w.psi,
                    "steps": {
                        sid: {
                            "state": s.state.value,
                            "assigned_agent_id": s.assigned_agent_id,
                            "attempts": s.attempts,
                            "error": s.error,
                        }
                        for sid, s in w.steps.items()
                    },
                }
                for w in self.workflows.values()
            ],
            "events": [asdict(e) for e in self.events],
        }
