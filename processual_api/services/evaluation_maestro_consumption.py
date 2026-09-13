"""Deterministic Maestro consumption for External Evaluation task outcomes.

The sandbox connector already proves the external operation and produces a safe
canonical task-injection envelope. This service performs the missing second
half: the ProcessualMaestroKernel actually consumes that safe outcome through a
real one-step workflow and returns a hash-only receipt suitable for durable
evidence. No raw task input, provider response, API key, or provider secret is
passed into Maestro.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from processual_kernel import (
    AgentSpec,
    MaestroAction,
    ProcessualMaestroKernel,
    StepState,
    TaskResult,
    WorkflowPlan,
    WorkflowStep,
)

MAESTRO_CONSUMPTION_SCHEMA_VERSION = "external-evaluation-maestro-consumption-v1"
_MAESTRO_CAPABILITY = "consume_evaluation_task"
_MAESTRO_AGENT_ID = "external-evaluation-consumer"


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class _EvaluationConsumptionRuntime:
    async def run(self, agent: AgentSpec, task: Any) -> TaskResult:
        metadata = dict(task.payload.get("metadata") or {})
        required = (
            "execution_evidence_sha256",
            "task_injection_sha256",
            "governance_trace_sha256",
            "task_id",
            "binding_id",
            "output_slot",
        )
        missing = [key for key in required if not str(metadata.get(key) or "").strip()]
        if missing:
            return TaskResult(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                ok=False,
                error=f"missing safe Maestro consumption metadata: {','.join(missing)}",
                latency_ms=0.0,
                cost=0.0,
            )
        consumed_material = {
            "schema_version": MAESTRO_CONSUMPTION_SCHEMA_VERSION,
            "execution_evidence_sha256": str(metadata["execution_evidence_sha256"]),
            "task_injection_sha256": str(metadata["task_injection_sha256"]),
            "governance_trace_sha256": str(metadata["governance_trace_sha256"]),
            "task_id": str(metadata["task_id"]),
            "binding_id": str(metadata["binding_id"]),
            "output_slot": str(metadata["output_slot"]),
            "response_sha256": str(metadata.get("response_sha256") or ""),
        }
        return TaskResult(
            task_id=task.task_id,
            agent_id=agent.agent_id,
            ok=True,
            output={
                "consumed": True,
                "consumption_sha256": _digest(consumed_material),
            },
            latency_ms=0.0,
            cost=0.0,
        )


async def consume_evaluation_task_with_maestro(
    *,
    execution_id: str,
    task_id: str,
    binding_id: str,
    output_slot: str,
    execution_evidence_sha256: str,
    task_injection_sha256: str,
    governance_trace_sha256: str,
    response_sha256: str | None = None,
) -> dict[str, Any]:
    """Run the safe external task outcome through an actual Maestro workflow."""

    safe_material = {
        "execution_id": str(execution_id or ""),
        "task_id": str(task_id or "").strip().lower(),
        "binding_id": str(binding_id or "").strip(),
        "output_slot": str(output_slot or "").strip(),
        "execution_evidence_sha256": str(execution_evidence_sha256 or "").strip(),
        "task_injection_sha256": str(task_injection_sha256 or "").strip(),
        "governance_trace_sha256": str(governance_trace_sha256 or "").strip(),
        "response_sha256": str(response_sha256 or "").strip(),
    }
    required = (
        "execution_id",
        "task_id",
        "binding_id",
        "output_slot",
        "execution_evidence_sha256",
        "task_injection_sha256",
        "governance_trace_sha256",
    )
    missing = [key for key in required if not safe_material[key]]
    if missing:
        raise RuntimeError(f"evaluation_maestro_consumption_material_incomplete:{','.join(missing)}")

    workflow_id = f"eval-maestro-{_digest(safe_material)[:24]}"
    maestro = ProcessualMaestroKernel(runtime=_EvaluationConsumptionRuntime())
    maestro.register_agent(
        AgentSpec(
            _MAESTRO_AGENT_ID,
            "Consumes safe External Evaluation task outcomes under Maestro governance",
            capabilities=(_MAESTRO_CAPABILITY,),
        )
    )
    maestro.create_workflow(
        WorkflowPlan(
            workflow_id=workflow_id,
            goal="Consume and attest the governed External Evaluation task outcome",
            priority=0.9,
            steps=(
                WorkflowStep(
                    "consume",
                    _MAESTRO_CAPABILITY,
                    "Consume the safe task-injection/evidence digest bundle",
                    metadata=safe_material,
                ),
            ),
        )
    )
    workflow = await maestro.run_workflow(workflow_id)
    step = workflow.steps["consume"]
    if step.state != StepState.COMPLETED or not isinstance(step.output, dict) or step.output.get("consumed") is not True:
        raise RuntimeError("evaluation_maestro_task_consumption_failed")

    maestro.intervene(
        workflow_id,
        MaestroAction.FINALIZE,
        "consume",
        "External Evaluation safe task outcome consumed and attested",
    )
    workflow = maestro.get_workflow(workflow_id)
    consumption_sha256 = str(step.output.get("consumption_sha256") or "")
    receipt_material = {
        "schema_version": MAESTRO_CONSUMPTION_SCHEMA_VERSION,
        "workflow_id": workflow_id,
        "workflow_state": workflow.state.value,
        "step_state": step.state.value,
        "agent_id": str(step.assigned_agent_id or ""),
        "task_id": safe_material["task_id"],
        "binding_id": safe_material["binding_id"],
        "output_slot": safe_material["output_slot"],
        "consumption_sha256": consumption_sha256,
        "execution_evidence_sha256": safe_material["execution_evidence_sha256"],
        "task_injection_sha256": safe_material["task_injection_sha256"],
        "governance_trace_sha256": safe_material["governance_trace_sha256"],
    }
    receipt_sha256 = _digest(receipt_material)
    return {
        **receipt_material,
        "receipt_sha256": receipt_sha256,
        "maestro_task_completed": True,
        "maestro_kernel": "ProcessualMaestroKernel",
        "raw_task_input_included": False,
        "raw_provider_response_included": False,
        "raw_secret_visible": False,
        "production_allowed": False,
    }


__all__ = [
    "MAESTRO_CONSUMPTION_SCHEMA_VERSION",
    "consume_evaluation_task_with_maestro",
]
