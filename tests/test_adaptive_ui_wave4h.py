from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from processual_kernel.adaptive.ui import (
    _safe,
    build_adaptive_dashboard_html,
    write_adaptive_dashboard_html,
)


class _Mode(Enum):
    REVIEW = "review"


@dataclass
class _Snapshot:
    workflow_id: str
    mode: _Mode
    recommendations: tuple[str, ...]
    nested: dict[str, object]


def test_safe_normalizes_dataclass_enum_sequences_and_mapping_keys() -> None:
    snapshot = _Snapshot(
        workflow_id="wf-1",
        mode=_Mode.REVIEW,
        recommendations=("inspect", "approve"),
        nested={1: [_Mode.REVIEW, ("x", "y")]},
    )

    result = _safe(snapshot)

    assert result == {
        "workflow_id": "wf-1",
        "mode": "review",
        "recommendations": ["inspect", "approve"],
        "nested": {1: ["review", ("x", "y")]},
    }
    assert _safe(_Mode.REVIEW) == "review"
    assert _safe((1, _Mode.REVIEW)) == [1, "review"]
    assert _safe([_Mode.REVIEW]) == ["review"]
    assert _safe({1: _Mode.REVIEW}) == {"1": "review"}
    assert _safe("plain") == "plain"


def test_build_dashboard_html_embeds_sorted_snapshot_payload_and_template_controls() -> None:
    html = build_adaptive_dashboard_html(
        {
            "workflow_id": "wf-9",
            "status": "quality-gate:attention",
            "counts": {"z": 2, "a": 1},
            "top_recommendations": ("review digest", "keep encrypted"),
            "risk": "high",
        }
    )

    assert '<script id="embedded-data" type="application/json">' in html
    assert '"counts": {"a": 1, "z": 2}' in html
    assert '"workflow_id": "wf-9"' in html
    assert '"top_recommendations": ["review digest", "keep encrypted"]' in html
    assert "quality-gate:attention" in html
    assert 'id="sample"' in html
    assert 'id="clear"' in html
    assert 'id="file"' in html
    assert "__DATA__" not in html


def test_build_dashboard_html_without_snapshot_embeds_empty_object() -> None:
    html = build_adaptive_dashboard_html()

    assert '<script id="embedded-data" type="application/json">{}</script>' in html
    assert "Maestro Adaptive Governance Dashboard" in html
    assert "const demo =" in html


def test_write_dashboard_html_creates_parent_and_returns_target(tmp_path) -> None:
    target = tmp_path / "nested" / "review" / "dashboard.html"
    snapshot = {"workflow_id": "wf-write", "risk": "medium"}

    result = write_adaptive_dashboard_html(snapshot, target)

    assert result == target
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert '"workflow_id": "wf-write"' in text
    assert '"risk": "medium"' in text
    assert "Maestro Adaptive Governance" in text
