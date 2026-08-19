from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "docs/qualification/VQ1_EXECUTION_PREPARATION_2026-08-19.md"


def _text() -> str:
    return PREP.read_text(encoding="utf-8")


def test_vq1_is_the_next_user_visible_milestone_before_real_staging() -> None:
    text = _text()

    assert "next user-visible qualification milestone" in text
    assert "VQ-1 Comprehensive Visual Review" in text
    assert "before any Real Staging qualification" in text
    assert "presented page-by-page and section-by-section" in text


def test_vq1_preparation_requires_exact_head_green_and_frozen_sha() -> None:
    text = _text()

    for gate in (
        "Packaging Qualification",
        "Program Release Qualification",
        "CAMARA Public Source Contracts",
        "Public Docker Build",
        "Sandbox Integration Qualification",
    ):
        assert gate in text

    assert "frozen exact source SHA" in text
    assert "browser capture tool and browser binary versions" in text


def test_vq1_preparation_locks_minimum_viewports_and_evidence_schema() -> None:
    text = _text()

    for viewport in (
        "1440 x 900",
        "1366 x 768",
        "390 x 844",
    ):
        assert viewport in text

    for field in (
        "source_sha",
        "browser_engine",
        "browser_version",
        "capture_tool_version",
        "route",
        "section",
        "state",
        "viewport",
        "locale",
        "evidence_id",
        "screenshot_path",
        "result",
        "defect_id",
    ):
        assert field in text


def test_vq1_preparation_requires_full_route_console_and_admin_discovery() -> None:
    text = _text()

    assert "This seed is not the final inventory" in text
    assert "every user-visible HTML route" in text
    assert "enumerate the delivered active navigation" in text
    assert "every active Admin navigation destination and nested section" in text
    assert "Legacy CGT Evaluator and Governor sections are not valid active targets" in text


def test_vq1_preparation_stops_broad_cleanup_at_visual_review_entry() -> None:
    text = _text()

    assert "presented for the comprehensive visual review" in text
    assert "rather than continuing broad cleanup" in text
    assert "Visual defects discovered by VQ-1 become the prioritized source-change backlog" in text
    assert "RealStagingQualified=false" in text
    assert "ProductionAuthorityGranted=false" in text
