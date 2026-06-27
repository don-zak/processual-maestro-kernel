"""Governance status routes — CGT governance reports and fate summaries."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/status")
async def governance_status():
    return {
        "mode": "controlled_adaptive",
        "active_policies": ["BalancedPolicy", "FastPolicy"],
        "drift_monitoring": True,
        "certification_level": "controlled_ready",
    }
