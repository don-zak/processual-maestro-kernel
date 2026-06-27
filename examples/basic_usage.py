from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from processual_kernel import AgentCriticality, AgentSpec, AgentTelemetry, ProcessualCGTKernel, TaskEnvelope, TaskResult
from processual_kernel.audit import JsonlAuditSink


class EchoRuntime:
    async def run(self, agent: AgentSpec, task: TaskEnvelope) -> TaskResult:
        return TaskResult(
            task_id=task.task_id, agent_id=agent.agent_id, ok=True,
            output={"handled_by": agent.agent_id}, cost=0.05,
        )


async def main() -> None:
    kernel = ProcessualCGTKernel(runtime=EchoRuntime(), audit_sink=JsonlAuditSink("audit/processual_cgt.jsonl"))

    kernel.register_agent(AgentSpec("planner", "plans workflows", capabilities=("planning",)))
    kernel.register_agent(AgentSpec("researcher", "researches facts", capabilities=("research",)))
    kernel.register_agent(
        AgentSpec("guardian", "safety gate", capabilities=("safety",), criticality=AgentCriticality.CRITICAL),
    )

    healthy = AgentTelemetry(
        success_rate=0.95, cooperation_success=0.90, useful_handoff_rate=0.8,
        demand_rate=0.90, business_priority=0.8, resource_cost=0.10,
    )
    bloated = AgentTelemetry(
        success_rate=0.25, cooperation_success=0.20, useful_handoff_rate=0.1,
        demand_rate=0.15, business_priority=0.2, resource_cost=0.90,
        overlap_score=0.90, failure_count=4, latency_p95_ms=9000,
    )
    risky = AgentTelemetry(
        success_rate=0.55, cooperation_success=0.50, useful_handoff_rate=0.4,
        demand_rate=0.95, business_priority=1.0, resource_cost=0.45,
        policy_risk=0.6, failure_count=3,
    )

    for agent_id, tel in [("planner", healthy), ("researcher", bloated), ("guardian", risky)]:
        decision = kernel.observe(agent_id, tel)
        print(
            agent_id, decision.new_state.value, round(decision.psi, 4),
            decision.reason, decision.requires_human_review,
        )

    result = await kernel.run_task(TaskEnvelope("t1", "planning", {"goal": "draft release plan"}, priority=0.9))
    print(result)
    print(kernel.snapshot())


if __name__ == "__main__":
    asyncio.run(main())
