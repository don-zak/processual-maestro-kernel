"""Full-flow demo: Agent Framework -> PMK Governance -> CGT Evaluation -> API.

Shows the complete pipeline end-to-end:
  1. A custom RuntimeAdapter simulating LangGraph
  2. Agent registration, telemetry intake, and governance decisions
  3. Full CGT structural transition evaluation
  4. HTTP API calls via FastAPI TestClient
  5. RuntimeAdapterRegistry management
"""
from __future__ import annotations

import locale
import sys

if locale.getpreferredencoding().upper() in ("CP1252", "ASCII"):
    sys.stdout.reconfigure(encoding="utf-8")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio

from cgtlib import CGTParameters, evaluate_structural_transition
from cgtlib.types import PhaseState
from processual_api.adapters.agent_runtime import (
    AgentExecutionResult,
    RuntimeAdapter,
    RuntimeHealth,
    runtime_registry,
)
from processual_kernel import AgentCriticality, AgentSpec, AgentTelemetry, ProcessualCGTKernel
from processual_kernel.audit import JsonlAuditSink


class LangGraphRuntime(RuntimeAdapter):
    """Simulates a LangGraph agent runtime connected via the universal adapter interface."""

    @property
    def framework_name(self) -> str:
        return "langgraph"

    async def run_agent(self, agent_id: str, task: dict, **kwargs) -> AgentExecutionResult:
        instruction = task.get("instruction", "")
        if "fail" in instruction.lower():
            return AgentExecutionResult(
                agent_id=agent_id, status="failed",
                error="simulated execution failure",
                telemetry={"latency_ms": 250.0, "tokens_used": 0},
            )
        return AgentExecutionResult(
            agent_id=agent_id, status="success",
            output={"agent": agent_id, "result": instruction},
            telemetry={"latency_ms": 120.0, "tokens_used": 450},
        )

    async def check_health(self) -> RuntimeHealth:
        return RuntimeHealth(
            available=True, framework="langgraph", version="0.2.30",
            diagnostics={"agents_online": 3, "queue_depth": 0},
        )

    async def list_agents(self) -> list[dict]:
        return [{"id": a, "status": "idle"} for a in ("agent-a", "agent-b", "agent-c")]


async def run_demo() -> None:
    # ── Step 1: Register adapter ──────────────────────────────────────────
    runtime_registry.register("langgraph", LangGraphRuntime())
    adapter = runtime_registry.get("langgraph")
    print("=== 1. Adapter Registration ===")
    print(f"Framework: {adapter.framework_name}")
    print(f"Health:    {await adapter.check_health()}")
    print(f"Agents:    {await adapter.list_agents()}")
    print(f"Registry:  {runtime_registry.list()}")
    print()

    # ── Step 2: Execution via adapter ─────────────────────────────────────
    result = await adapter.run_agent("agent-a", {"instruction": "research vector store options"})
    print("=== 2. Agent Execution ===")
    print(f"Status: {result.status} | Output: {result.output}")
    fail_result = await adapter.run_agent("agent-b", {"instruction": "fail intentionally"})
    print(f"Failure: {fail_result.status} | Error: {fail_result.error}")
    print()

    # ── Step 3: PMK Governance ────────────────────────────────────────────
    print("=== 3. PMK Governance ===")
    kernel = ProcessualCGTKernel(runtime=adapter, audit_sink=JsonlAuditSink("/dev/null"))

    kernel.register_agent(AgentSpec("agent-a", "research agent", capabilities=("research",)))
    kernel.register_agent(AgentSpec("agent-b", "critical safety agent", capabilities=("safety",),
                                     criticality=AgentCriticality.CRITICAL))
    kernel.register_agent(AgentSpec("agent-c", "high-demand agent", capabilities=("action",)))

    telemetry_samples = {
        "agent-a": AgentTelemetry(
            success_rate=0.95, cooperation_success=0.90, useful_handoff_rate=0.80,
            demand_rate=0.60, business_priority=0.70, resource_cost=0.15,
        ),
        "agent-b": AgentTelemetry(
            success_rate=0.55, cooperation_success=0.50, useful_handoff_rate=0.40,
            demand_rate=0.95, business_priority=1.0, resource_cost=0.45,
            policy_risk=0.6, failure_count=3,
        ),
        "agent-c": AgentTelemetry(
            success_rate=0.30, cooperation_success=0.25, useful_handoff_rate=0.15,
            demand_rate=0.90, business_priority=0.90, resource_cost=0.80,
            overlap_score=0.85, failure_count=5, latency_p95_ms=12000,
        ),
    }

    for agent_id, tel in telemetry_samples.items():
        decision = kernel.observe(agent_id, tel)
        print(f"  {agent_id:8s} -> {decision.new_state.value:15s}  "
              f"Psi={decision.psi:.4f}  {decision.reason}")

    snapshot = kernel.snapshot()
    print(f"\n  Kernel snapshot: {len(snapshot)} agents tracked")
    for s in snapshot:
        print(f"    {s['agent_id']:8s} state={s['state']:15s} psi={s['psi']:.4f} failures={s['failure_streak']}")
    print()

    # ── Step 4: Direct CGT Evaluation ─────────────────────────────────────
    print("=== 4. CGT Structural Transition ===")
    report = evaluate_structural_transition(
        source_phase=PhaseState(phase_id="source", mass=1.0, mean_retention=0.60,
                                harmony=0.70, fatigue=0.30, self_potential=0.50),
        target_phase=PhaseState(phase_id="target", mass=1.2, mean_retention=0.75,
                                harmony=0.85, fatigue=0.20, self_potential=0.70),
        gate_openness=0.55,
        carrying_capacity=0.80,
        node_fatigue=0.25,
        local_safety=0.75,
        continuation_channel=0.65,
        tau=0.40,
        tau_star=0.60,
        trigger=0.50,
        source_features={"stability": 0.7, "coherence": 0.6, "adaptability": 0.5},
        target_features={"stability": 0.8, "coherence": 0.7, "adaptability": 0.9},
        params=CGTParameters(),
    )
    fv = report.fate_vector
    print(f"  Fate:        stability={fv.stability:.3f}, "
          f"hybridity={fv.hybridity:.3f}, "
          f"distortion={fv.distortion:.3f}")
    print(f"               extinction={fv.extinction:.3f}, "
          f"collapse={fv.collapse:.3f}, "
          f"flourishing={fv.flourishing:.3f}")
    print(f"  Rank:        {report.existence_rank.value}")
    print(f"  Transmissibility: {report.transmissibility:.3f}")
    print(f"  Retention:        {report.retention:.3f}")
    print(f"  Lock state:       {report.lock_state.locked}")
    print()

    # ── Step 5: API Interaction ──────────────────────────────────────────
    print("=== 5. HTTP API (/cgt/evaluate) ===")
    try:
        from httpx import ASGITransport, AsyncClient

        from processual_api.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/cgt/evaluate", json={
                "transition_channel": 0.65,
                "compatibility": 0.72,
                "retention": 0.58,
                "harmony": 0.80,
                "fatigue": 0.25,
                "complexity": 0.40,
                "shock": 0.10,
                "dwell_time": 5.0,
                "carrier": 0.70,
                "diversity": 0.60,
                "novelty": 0.55,
                "lift": 0.30,
            })
            data = resp.json()
            print(f"  Status: {resp.status_code}")
            print(f"  Fate:   {data['fate_vector']}")
            print(f"  Rank:   {data['existence_rank']}")
    except ImportError:
        print("  (httpx not installed — skipping API call)")
    except Exception as e:
        print(f"  (API call skipped: {e})")

    print()
    print("=== Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(run_demo())
