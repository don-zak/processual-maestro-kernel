"""Route-level authorization hardening for CGT external evaluation access.

Commercial callers keep the normal Maestro-unit quota path. Governed External
Evaluation keys are already bounded atomically by their credential-use limit at
authentication time, so they must not be charged a second time through the
commercial quota store.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Request

from ..auth.security import require_quota, require_scope
from . import cgt_governor as cgt


def _is_external_evaluation(current_user: dict[str, Any]) -> bool:
    return (
        current_user.get("auth_method") == "api_key"
        and current_user.get("entitlement_source") == "admin_evaluation_grant"
        and current_user.get("subscription_required") is False
    )


async def _consume_quota(
    request: Request,
    current_user: dict[str, Any],
    *,
    item_count: int | None = None,
) -> dict[str, Any]:
    if _is_external_evaluation(current_user):
        return current_user
    if item_count is not None:
        request.state.pricing_item_count = item_count
    quota_dependency = require_quota("evaluation")
    return await quota_dependency(request, current_user)


def _require_scoped_quota(required_scope: str):
    async def _dependency(
        request: Request,
        current_user: dict[str, Any] = Depends(require_scope(required_scope)),
    ) -> dict[str, Any]:
        return await _consume_quota(request, current_user)

    return _dependency


def _route_matches(route: Any, path: str, method: str) -> bool:
    methods = getattr(route, "methods", set()) or set()
    return getattr(route, "path", "") == path and method.upper() in methods


_REPLACED_ROUTES = {
    ("/cgt/govern", "POST"),
    ("/cgt/govern/batch", "POST"),
    ("/cgt/govern/repair", "POST"),
    ("/cgt/govern/auto-repair", "POST"),
    ("/cgt/govern/compare", "POST"),
    ("/cgt/govern/report", "POST"),
    ("/cgt/govern/simulate", "POST"),
    ("/cgt/analyze", "POST"),
    ("/cgt/govern/gateway/evaluate", "POST"),
    ("/cgt/govern/toggle", "POST"),
    ("/cgt/govern/gateway/agents", "POST"),
    ("/cgt/govern/gateway/agents/{agent_id}/action", "POST"),
}

cgt.router.routes = [
    route
    for route in cgt.router.routes
    if not any(
        _route_matches(route, path, method)
        for path, method in _REPLACED_ROUTES
    )
]


@cgt.router.post("/cgt/govern")
async def guarded_govern(
    req: cgt.GovernRequest,
    current_user: dict[str, Any] = Depends(_require_scoped_quota("run:govern")),
):
    return await cgt.govern(req, current_user)


@cgt.router.post("/cgt/govern/batch")
async def guarded_govern_batch(
    req: cgt.BatchGovernRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(require_scope("run:govern")),
):
    checked_user = await _consume_quota(
        request,
        current_user,
        item_count=len(req.answers),
    )
    return await cgt.govern_batch(req, checked_user)


@cgt.router.post("/cgt/govern/repair")
async def guarded_generate_repair(
    req: cgt.RepairRequest,
    current_user: dict[str, Any] = Depends(require_scope("run:govern")),
):
    return await cgt.generate_repair(req, current_user)


@cgt.router.post("/cgt/govern/auto-repair")
async def guarded_auto_repair(
    req: cgt.AutoRepairRequest,
    current_user: dict[str, Any] = Depends(_require_scoped_quota("run:govern")),
):
    return await cgt.auto_repair(req, current_user)


@cgt.router.post("/cgt/govern/compare")
async def guarded_compare_adapters(
    req: cgt.CompareAdaptersRequest,
    current_user: dict[str, Any] = Depends(_require_scoped_quota("run:compare")),
):
    return await cgt.compare_adapters(req, current_user)


@cgt.router.post("/cgt/govern/report")
async def guarded_govern_report(
    req: cgt.ReportRequest,
    current_user: dict[str, Any] = Depends(_require_scoped_quota("create:reports")),
):
    return await cgt.govern_report(req, current_user)


@cgt.router.post("/cgt/govern/simulate")
async def guarded_run_simulation(
    current_user: dict[str, Any] = Depends(_require_scoped_quota("run:govern")),
):
    return await cgt.run_simulation(current_user)


@cgt.router.post("/cgt/analyze")
async def guarded_analyze(
    req: cgt.AnalyzeRequest,
    current_user: dict[str, Any] = Depends(_require_scoped_quota("run:analyze")),
):
    return await cgt.analyze(req, current_user)


@cgt.router.post("/cgt/govern/gateway/evaluate")
async def guarded_gateway_evaluate(
    req: cgt.GatewayEvaluateRequest,
    current_user: dict[str, Any] = Depends(_require_scoped_quota("run:govern")),
):
    return await cgt.gateway_evaluate(req, current_user)


@cgt.router.post("/cgt/govern/toggle")
async def guarded_governor_toggle(
    req: cgt.ToggleRequest,
    current_user: dict[str, Any] = Depends(require_scope("admin:settings")),
):
    return await cgt.governor_toggle(req, current_user)


@cgt.router.post("/cgt/govern/gateway/agents")
async def guarded_gateway_register_agent(
    req: cgt.RegisterAgentRequest,
    current_user: dict[str, Any] = Depends(require_scope("admin:settings")),
):
    return await cgt.gateway_register_agent(req, current_user)


@cgt.router.post("/cgt/govern/gateway/agents/{agent_id}/action")
async def guarded_gateway_agent_action(
    agent_id: str,
    req: cgt.AgentActionRequest,
    current_user: dict[str, Any] = Depends(require_scope("admin:settings")),
):
    return await cgt.gateway_agent_action(agent_id, req, current_user)


__all__ = ["_REPLACED_ROUTES", "_is_external_evaluation"]
