"""Workflow routes — CRUD and governance operations for kernel workflows."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from processual_kernel import AgentSpec, ProcessualMaestroKernel, WorkflowPlan, WorkflowStep

from ..auth.security import get_current_user
from ..cgt_governor.adapters.execution_fanout import ExecutionFanoutSaturatedError
from ..cgt_governor.adapters.registry import adapter_registry
from ..cgt_governor.policy.fanout_planner import (
    execute_fanout_plan,
    plan_fanout_execution,
)
from ..cgt_governor.policy.orchestration_metrics import (
    OrchestrationObservation,
    record_orchestration,
)
from ..dependencies import get_kernel

router = APIRouter(prefix="/workflows", tags=["workflows"])


class CreateWorkflowRequest(BaseModel):
    workflow_id: str
    goal: str
    steps: list[dict]


class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str
    step_count: int


class CheckpointResponse(BaseModel):
    workflow_id: str
    checkpoint_number: int
    status: str


class WorkflowDetailResponse(BaseModel):
    workflow_id: str
    status: str
    steps: dict
    agents: list


class GovernanceReport(BaseModel):
    workflow_id: str
    runtime_mode: str
    policy: str


class LLMOrchestrationRequest(BaseModel):
    provider: str
    prompts: list[str]
    system_prompt: str = ""
    max_tokens: int = 512
    temperature: float = 0.7


@router.post("", response_model=WorkflowResponse)
async def create_workflow(
    req: CreateWorkflowRequest,
    _user: str = Depends(get_current_user),
    kernel: ProcessualMaestroKernel = Depends(get_kernel),
):
    try:
        kernel.register_agent(AgentSpec("default-agent", "work", capabilities=("work",)))
    except ValueError as exc:
        # Repeated API calls in the same process should not fail just because the
        # built-in workflow agent has already been registered.  Keep other
        # registration errors visible as 400 responses.
        if "agent already registered" not in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    steps = tuple(
        WorkflowStep(s.get("id", f"step_{i}"), s.get("agent_type", "work"), s.get("description", ""))
        for i, s in enumerate(req.steps)
    )
    plan = WorkflowPlan(
        workflow_id=req.workflow_id,
        goal=req.goal,
        metadata={},
        steps=steps,
    )
    try:
        record = kernel.create_workflow(plan)
    except ValueError as exc:
        # Integration and release-check suites may reuse deterministic workflow IDs
        # across repeated runs against the same process-level kernel.  Treat an
        # already-created workflow as an idempotent create request instead of
        # leaking a 500 response.  Other validation errors remain client errors.
        if "workflow already exists" not in str(exc):
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            record = kernel.get_workflow(req.workflow_id)
        except KeyError as inner_exc:  # defensive: should not happen after the create collision
            raise HTTPException(
                status_code=500,
                detail=f"workflow exists but cannot be loaded: {req.workflow_id}",
            ) from inner_exc

    return WorkflowResponse(
        workflow_id=record.plan.workflow_id,
        status=record.state.value if hasattr(record.state, "value") else str(record.state),
        step_count=len(record.steps),
    )


@router.post("/llm-orchestration", response_model=None)
async def orchestrate_llm(
    req: LLMOrchestrationRequest,
    _user: str = Depends(get_current_user),
) -> dict[str, object] | Response:
    """Fan out workflow prompts through one configured LLM provider safely.

    The request-local planner may pace broad single-provider workloads, while the
    shared execution fan-out governor remains the authoritative saturation layer.
    """
    width = len(req.prompts)
    if width < 1 or width > 32:
        raise HTTPException(status_code=400, detail="prompts must contain between 1 and 32 items")
    if any(not prompt.strip() for prompt in req.prompts):
        raise HTTPException(status_code=400, detail="prompts must not contain empty items")
    if req.max_tokens < 1 or req.max_tokens > 8192:
        raise HTTPException(status_code=400, detail="max_tokens must be between 1 and 8192")
    if req.temperature < 0.0 or req.temperature > 2.0:
        raise HTTPException(status_code=400, detail="temperature must be between 0 and 2")

    adapter = adapter_registry.get(req.provider)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"unknown LLM provider: {req.provider}")
    if not adapter.is_configured():
        raise HTTPException(status_code=409, detail=f"LLM provider is not configured: {req.provider}")

    plan = plan_fanout_execution(width=width, provider_count=1)
    started = time.perf_counter()

    async def generate(prompt: str) -> str:
        return await adapter.generate(
            prompt=prompt,
            system_prompt=req.system_prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )

    outcomes = await execute_fanout_plan(req.prompts, generate, plan)
    latency_seconds = time.perf_counter() - started
    saturated = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, ExecutionFanoutSaturatedError)
    ]
    if saturated:
        record_orchestration(
            OrchestrationObservation(
                paced=plan.is_paced,
                plan_reason=plan.reason,
                width=width,
                outcome="saturated",
                latency_seconds=latency_seconds,
                success_items=0,
                error_items=len(outcomes),
            )
        )
        return Response(
            status_code=429,
            headers={
                "Retry-After": "1",
                "X-Maestro-Capacity-Reason": "execution_fanout",
            },
        )

    results: list[dict[str, object]] = []
    success_items = 0
    error_items = 0
    for index, outcome in enumerate(outcomes):
        if isinstance(outcome, BaseException):
            error_items += 1
            results.append(
                {
                    "index": index,
                    "status": "error",
                    "error_type": type(outcome).__name__,
                }
            )
        else:
            success_items += 1
            results.append(
                {
                    "index": index,
                    "status": "success",
                    "response": outcome,
                }
            )

    record_orchestration(
        OrchestrationObservation(
            paced=plan.is_paced,
            plan_reason=plan.reason,
            width=width,
            outcome="partial_error" if error_items else "success",
            latency_seconds=latency_seconds,
            success_items=success_items,
            error_items=error_items,
        )
    )

    return {
        "provider": req.provider,
        "width": width,
        "paced": plan.is_paced,
        "local_parallelism": plan.local_parallelism,
        "plan_reason": plan.reason,
        "results": results,
    }


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(
    workflow_id: str, _user: str = Depends(get_current_user), kernel: ProcessualMaestroKernel = Depends(get_kernel)
):
    try:
        record = kernel.get_workflow(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"workflow not found: {workflow_id}")
    return WorkflowDetailResponse(
        workflow_id=record.plan.workflow_id,
        status=record.state.value if hasattr(record.state, "value") else str(record.state),
        steps={},
        agents=[],
    )


@router.post("/{workflow_id}/checkpoint", response_model=CheckpointResponse)
async def create_checkpoint(
    workflow_id: str, _user: str = Depends(get_current_user), kernel: ProcessualMaestroKernel = Depends(get_kernel)
):
    try:
        kernel.get_workflow(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"workflow not found: {workflow_id}")
    return CheckpointResponse(
        workflow_id=workflow_id,
        checkpoint_number=1,
        status="created",
    )


@router.get("/{workflow_id}/governance", response_model=GovernanceReport)
async def get_governance(
    workflow_id: str, _user: str = Depends(get_current_user), kernel: ProcessualMaestroKernel = Depends(get_kernel)
):
    try:
        kernel.get_workflow(workflow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"workflow not found: {workflow_id}")
    return GovernanceReport(
        workflow_id=workflow_id,
        runtime_mode="controlled_adaptive",
        policy="BalancedPolicy",
    )
