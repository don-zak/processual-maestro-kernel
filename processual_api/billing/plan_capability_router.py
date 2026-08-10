from __future__ import annotations

from fastapi import APIRouter, HTTPException

from processual_api.billing.assessment_plan_fulfillment import (
    assessment_plan_fulfillment_payload,
)
from processual_api.billing.plan_capability_matrix import plan_capability_payload

router = APIRouter(prefix="/billing")


def _assessment_capability_payload(plan_code: str) -> dict[str, object]:
    fulfillment = assessment_plan_fulfillment_payload(plan_code)
    source_plan = str(fulfillment["entitlement_source_plan_code"])
    payload = plan_capability_payload(source_plan)
    payload["plan_code"] = plan_code.strip().lower().replace("-", "_")
    payload["entitlement_source_plan_code"] = source_plan
    payload["assessment_fulfillment"] = fulfillment
    payload["activation_requires_assessment"] = True
    return payload


@router.get("/plan-capabilities/{plan_code}")
async def get_plan_capabilities(plan_code: str) -> dict[str, object]:
    try:
        return plan_capability_payload(plan_code)
    except KeyError:
        try:
            return _assessment_capability_payload(plan_code)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Unknown plan.") from exc


__all__ = ["get_plan_capabilities", "router"]
