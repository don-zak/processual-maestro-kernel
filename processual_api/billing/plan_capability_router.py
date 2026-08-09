from __future__ import annotations

from fastapi import APIRouter, HTTPException

from processual_api.billing.plan_capability_matrix import plan_capability_payload

router = APIRouter(prefix="/billing")


@router.get("/plan-capabilities/{plan_code}")
async def get_plan_capabilities(plan_code: str) -> dict[str, object]:
    try:
        return plan_capability_payload(plan_code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown plan.") from exc


__all__ = ["get_plan_capabilities", "router"]
