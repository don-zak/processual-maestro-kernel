from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
from pprint import pprint

from processual_kernel import (
    AgentCriticality,
    AgentSpec,
    ProcessualMaestroKernel,
    TaskResult,
    WorkflowPlan,
    WorkflowStep,
)


class DemoRuntime:
    async def run(self, agent, task):
        instruction = task.payload.get("instruction", "")
        if "fail" in instruction.lower():
            return TaskResult(task.task_id, agent.agent_id, ok=False, error="demo failure", latency_ms=120, cost=0.3)
        return TaskResult(
            task_id=task.task_id,
            agent_id=agent.agent_id,
            ok=True,
            output={"agent": agent.agent_id, "done": instruction},
            latency_ms=80,
            cost=0.12,
        )


async def main():
    maestro = ProcessualMaestroKernel(runtime=DemoRuntime())
    maestro.register_agent(AgentSpec("planner", "plans work", capabilities=("plan",)))
    maestro.register_agent(AgentSpec("researcher", "researches context", capabilities=("research",)))
    maestro.register_agent(AgentSpec("coder", "implements code", capabilities=("code",)))
    maestro.register_agent(
        AgentSpec("reviewer", "reviews output", capabilities=("review",), criticality=AgentCriticality.HIGH),
    )

    plan = WorkflowPlan(
        workflow_id="wf-demo",
        goal="Build a small agent workflow under maestro supervision",
        priority=0.85,
        steps=(
            WorkflowStep("s1", "plan", "Break down the goal"),
            WorkflowStep("s2", "research", "Collect constraints", depends_on=("s1",)),
            WorkflowStep("s3", "code", "Implement the kernel adapter", depends_on=("s2",)),
            WorkflowStep("s4", "review", "Review the final result", depends_on=("s3",)),
        ),
    )
    maestro.create_workflow(plan)
    workflow = await maestro.run_workflow("wf-demo")
    print("WORKFLOW:", workflow.state.value, "psi=", round(workflow.psi, 4))
    pprint(maestro.maestro_snapshot())


if __name__ == "__main__":
    asyncio.run(main())
