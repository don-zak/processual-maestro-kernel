"""Deterministic Maestro consumption for External Evaluation task outcomes.

The sandbox connector proves the external operation and produces a safe canonical
Task Injection envelope. CGT governance is already enforced *before admission* by
the External Evaluation governance layer. This service performs the missing
second half: ProcessualMaestroKernel actually consumes the safe outcome through a
real one-step workflow and returns a hash-only receipt suitable for durable
evidence.

The public External Evaluation build intentionally does not ship the private
``cgtlib`` structural-transition engine. Therefore this consumer must not invoke
the kernel's private-CGT observation path a second time after admission. It uses
ProcessualMaestroKernel for workflow creation, delegation, runtime execution,
step completion and finalization, while the already-committed External Evaluation
CGT decision remains the authoritative governance proof.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from processual_kernel import (
    AgentSpec,
    MaestroAction,
    ProcessualMaestroKernel,
    StepState,
    TaskResult,
    WorkflowPlan,
    WorkflowState,
    WorkflowStep,
)

MAESTRO_CONSUMPTION_SCHEMA_VERSION = "external-evaluation-maestro-consumption-v2"
MAESTRO_GOVERNANCE_SOURCE = "external_evaluation_cgt_prevalidated"
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
            "governance_source": MAESTRO_GOVERNANCE_SOURCE,
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


class _EvaluationMaestroKernel(ProcessualMaestroKernel):
    """ProcessualMaestroKernel adapter for a CGT-prevalidated Evaluation task.

    The normal kernel observation path calls private ``cgtlib`` structural
    transition evaluation. That engine is intentionally absent from the public
    External Evaluation build. Governance has already happened before admission,
    so repeating a private CGT evaluation here is neither required nor desirable.

    This adapter changes only the *observation* hooks. Delegation, agent routing,
    task execution, step state transitions, workflow lifecycle, events and
    finalization still run through ProcessualMaestroKernel.
    """

    def observe(self, agent_id: str, telemetry: Any) -> None:  # type: ignore[override]
        record = self.get_agent(agent_id)
        record.failure_streak = int(getattr(telemetry, "failure_count", 0) or 0)
        record.observations += 1
        record.last_updated_at = time.time()
        return None

    def _observe_workflow_from_steps(self, workflow: Any) -> None:  # type: ignore[override]
        steps = list(workflow.steps.values())
        if steps and all(step.state == StepState.COMPLETED for step in steps):
            workflow.state = WorkflowState.COMPLETED
            action = MaestroAction.FINALIZE
            reason = "all CGT-prevalidated Evaluation workflow steps completed"
        elif any(step.state == StepState.FAILED for step in steps):
            workflow.state = WorkflowState.FAILED
            action = MaestroAction.REROUTE
            reason = "CGT-prevalidated Evaluation workflow step failed"
        else:
            workflow.state = WorkflowState.RUNNING
            action = MaestroAction.OBSERVE
            reason = "CGT-prevalidated Evaluation workflow in progress"
        workflow.updated_at = time.time()
        self.emit(
            workflow.plan.workflow_id,
            action,
            workflow.plan.workflow_id,
            reason,
            {"governance_source": MAESTRO_GOVERNANCE_SOURCE},
        )
        return None


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
    """Run the safe external task outcome through a real Maestro workflow."""

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
    maestro = _EvaluationMaestroKernel(runtime=_EvaluationConsumptionRuntime())
    maestro.register_agent(
        AgentSpec(
            _MAESTRO_AGENT_ID,
            "Consumes safe External Evaluation task outcomes under pre-admission CGT governance",
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
            metadata={"governance_source": MAESTRO_GOVERNANCE_SOURCE},
        )
    )
    workflow = await maestro.run_workflow(workflow_id)
    step = workflow.steps["consume"]
    if (
        workflow.state != WorkflowState.COMPLETED
        or step.state != StepState.COMPLETED
        or not isinstance(step.output, dict)
        or step.output.get("consumed") is not True
    ):
        raise RuntimeError("evaluation_maestro_task_consumption_failed")

    maestro.intervene(
        workflow_id,
        MaestroAction.FINALIZE,
        "consume",
        "External Evaluation safe task outcome consumed and attested",
        {"governance_source": MAESTRO_GOVERNANCE_SOURCE},
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
        "governance_source": MAESTRO_GOVERNANCE_SOURCE,
        "private_cgt_re_evaluation_required": False,
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
    "MAESTRO_GOVERNANCE_SOURCE",
    "consume_evaluation_task_with_maestro",
]
