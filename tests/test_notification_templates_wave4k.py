from __future__ import annotations

import pytest

from processual_kernel.notifications.templates import (
    _color_for_rank,
    deployment_alert_embed,
    fate_alert_embed,
    security_alert_embed,
    workflow_alert_embed,
)


@pytest.mark.parametrize(
    ("rank", "expected_color"),
    (
        ("flourishing", 5763719),
        ("stable", 5814783),
        ("hybrid", 16753920),
        ("distorted", 15158332),
        ("transient", 16744272),
        ("extinct", 15548997),
        ("STABLE", 5814783),
        ("unknown", 5814783),
    ),
)
def test_color_for_rank_known_case_insensitive_and_default(
    rank: str,
    expected_color: int,
) -> None:
    assert _color_for_rank(rank) == expected_color


def test_fate_alert_embed_formats_scores_and_recommendation() -> None:
    embed = fate_alert_embed(
        "hybrid",
        stability=0.876,
        distortion=0.123,
        extinction=0.5,
        recommendation="Monitor transition",
    )

    assert embed == {
        "title": "CGT Fate: hybrid",
        "color": 16753920,
        "fields": [
            {"name": "Stability", "value": "0.88", "inline": True},
            {"name": "Distortion", "value": "0.12", "inline": True},
            {"name": "Extinction", "value": "0.50", "inline": True},
            {
                "name": "Recommendation",
                "value": "Monitor transition",
                "inline": False,
            },
        ],
    }


def test_workflow_alert_embed_preserves_runtime_state() -> None:
    assert workflow_alert_embed("wf-42", "blocked", "supervised") == {
        "title": "Workflow wf-42",
        "color": 5814783,
        "fields": [
            {"name": "Status", "value": "blocked", "inline": True},
            {"name": "Runtime Mode", "value": "supervised", "inline": True},
        ],
    }


def test_security_alert_embed_marks_description_non_inline() -> None:
    assert security_alert_embed("policy_violation", "Denied unsafe transition") == {
        "title": "Security: policy_violation",
        "color": 15548997,
        "fields": [
            {
                "name": "Description",
                "value": "Denied unsafe transition",
                "inline": False,
            }
        ],
    }


@pytest.mark.parametrize(
    ("status", "expected_color"),
    (("success", 5814783), ("failed", 15158332), ("SUCCESS", 15158332)),
)
def test_deployment_alert_embed_status_color_branch(
    status: str,
    expected_color: int,
) -> None:
    embed = deployment_alert_embed("v2.4.0", "production", status)

    assert embed["title"] == "Deployment v2.4.0 to production"
    assert embed["color"] == expected_color
    assert embed["fields"] == [
        {"name": "Version", "value": "v2.4.0", "inline": True},
        {"name": "Environment", "value": "production", "inline": True},
        {"name": "Status", "value": status, "inline": True},
    ]
