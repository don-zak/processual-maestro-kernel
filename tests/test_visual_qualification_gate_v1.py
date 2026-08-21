from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VQ1 = ROOT / "docs/qualification/VISUAL_QUALIFICATION_GATE_V1.md"


def _text() -> str:
    return VQ1.read_text(encoding="utf-8")


def test_visual_qualification_gate_is_required_before_real_staging() -> None:
    text = _text()

    assert "REQUIRED PRE-REAL-STAGING QUALIFICATION GATE" in text
    assert "release-truth reconciliation -> VQ-1 -> Real Staging qualification" in text
    assert "VQ-1 is intentionally before Real Staging" in text


def test_visual_gate_requires_zero_unreviewed_pages_and_sections() -> None:
    text = _text()

    assert "zero unreviewed user-visible pages" in text
    assert "zero unreviewed active sections" in text
    assert "route inventory has zero unreviewed user-visible pages" in text
    assert "Console inventory has zero unreviewed active sections" in text
    assert "Admin inventory has zero unreviewed active sections" in text


def test_visual_gate_covers_current_public_routes_and_active_console_sections() -> None:
    text = _text()

    for route in (
        "/",
        "/login",
        "/plans",
        "/offer/starter",
        "/register",
        "/verify-email",
        "/pricing",
        "/console/",
        "/admin",
    ):
        assert f"`{route}`" in text

    for section in (
        "Overview",
        "Workflows",
        "Governance",
        "Telemetry",
        "Reports",
        "Gateway",
        "Simulation",
        "Settings",
    ):
        assert f"- {section};" in text


def test_visual_gate_requires_state_viewport_locale_and_screenshot_evidence() -> None:
    text = _text()

    for required in (
        "desktop and narrow viewport",
        "loading",
        "empty/no-data",
        "permission denied/insufficient scope",
        "unavailable/fail-closed",
        "localization/RTL",
        "Screenshots or browser captures",
        "source_sha",
        "evidence_id",
    ):
        assert required in text


def test_visual_gate_preserves_quarantine_and_private_math_boundary() -> None:
    text = _text()

    assert "Legacy CGT Evaluator and Governor sections are not active visual targets" in text
    assert "quarantined legacy UI remains absent" in text
    assert "no private mathematical implementation detail is exposed" in text
    assert "RealStagingQualified=false" in text
    assert "ProductionAuthorityGranted=false" in text
