from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processual_kernel import (
    AdaptiveGovernanceToolkit,
    AgentSpec,
    HandoffTelemetry,
    ProcessualMaestroKernel,
    WorkflowPlan,
    WorkflowStep,
    WorkflowTelemetry,
)

kernel = ProcessualMaestroKernel()
kernel.register_agent(AgentSpec("researcher", "research", capabilities=("research",)))
kernel.register_agent(AgentSpec("writer", "write", capabilities=("write",)))

plan = WorkflowPlan(
    workflow_id="wf_adaptive_demo",
    goal="Generate a market research report",
    metadata={"duration": "long", "estimated_minutes": 90, "risk": "medium"},
    steps=(
        WorkflowStep("research", "research", "Collect evidence"),
        WorkflowStep("write", "write", "Draft report", depends_on=("research",)),
    ),
)
workflow = kernel.create_workflow(plan)
workflow.steps["research"].assigned_agent_id = "researcher"
workflow.steps["write"].assigned_agent_id = "writer"

kernel.observe_handoff(
    "researcher",
    "writer",
    HandoffTelemetry(
        artifact_quality=0.25, context_preservation=0.3, acceptance_rate=0.25,
        rework_rate=0.7, ambiguity=0.8,
    ),
)

toolkit = AdaptiveGovernanceToolkit(kernel)
cycle = toolkit.pulse_adaptive(
    plan.workflow_id,
    telemetry=WorkflowTelemetry(progress_rate=0.35, coordination_quality=0.4, blocking_rate=0.2),
    event="handoff_degradation",
)

print("profile:", cycle.profile.duration.value, cycle.profile.risk.value)
print("policy:", cycle.policy.name.value, cycle.policy.policy_version)
print("tempo:", cycle.tempo.tempo.value)
print("checkpoint:", cycle.checkpoint.kind.value if cycle.checkpoint else None)
print("handoff suggestions:", len(cycle.handoff_suggestions))
print("critique findings:", cycle.policy_critique.findings if cycle.policy_critique else ())
print("metrics:", toolkit.metrics_snapshot())
