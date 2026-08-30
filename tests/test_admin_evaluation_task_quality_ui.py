from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_SCRIPT = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_coverage.js"


def test_admin_coverage_ui_shows_semantic_task_quality_separately() -> None:
    source = COVERAGE_SCRIPT.read_text(encoding="utf-8")

    for marker in [
        "/settings/admin/evaluation-grants/task-quality-status",
        "Semantic task quality:",
        "Semantic Task Outcomes",
        "outcome passes",
        "outcome failures",
        "missing/incomplete",
        "semantic_quality_sufficient",
        "idempotency evidence",
    ]:
        assert marker in source

    assert "complete && qualityPassed && semanticPassed" in source
    assert "task completion is not evaluation success" in source
    assert "method: 'POST'" not in source
    assert "method: 'DELETE'" not in source
