from __future__ import annotations

from typing import Any


def fate_alert_embed(
    rank: str, stability: float, distortion: float, extinction: float, recommendation: str
) -> dict[str, Any]:
    return {
        "title": f"CGT Fate: {rank}",
        "color": _color_for_rank(rank),
        "fields": [
            {"name": "Stability", "value": f"{stability:.2f}", "inline": True},
            {"name": "Distortion", "value": f"{distortion:.2f}", "inline": True},
            {"name": "Extinction", "value": f"{extinction:.2f}", "inline": True},
            {"name": "Recommendation", "value": recommendation, "inline": False},
        ],
    }


def workflow_alert_embed(workflow_id: str, status: str, runtime_mode: str) -> dict[str, Any]:
    return {
        "title": f"Workflow {workflow_id}",
        "color": 5814783,
        "fields": [
            {"name": "Status", "value": status, "inline": True},
            {"name": "Runtime Mode", "value": runtime_mode, "inline": True},
        ],
    }


def security_alert_embed(alert_type: str, description: str) -> dict[str, Any]:
    return {
        "title": f"Security: {alert_type}",
        "color": 15548997,
        "fields": [
            {"name": "Description", "value": description, "inline": False},
        ],
    }


def deployment_alert_embed(version: str, environment: str, status: str) -> dict[str, Any]:
    return {
        "title": f"Deployment {version} to {environment}",
        "color": 5814783 if status == "success" else 15158332,
        "fields": [
            {"name": "Version", "value": version, "inline": True},
            {"name": "Environment", "value": environment, "inline": True},
            {"name": "Status", "value": status, "inline": True},
        ],
    }


def _color_for_rank(rank: str) -> int:
    colors = {
        "flourishing": 5763719,
        "stable": 5814783,
        "hybrid": 16753920,
        "distorted": 15158332,
        "transient": 16744272,
        "extinct": 15548997,
    }
    return colors.get(rank.lower(), 5814783)
