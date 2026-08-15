from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "processual_api" / "static" / "js"
COVERAGE_SCRIPT = JS / "admin_evaluation_coverage.js"
SESSION_SCRIPT = JS / "admin_session.js"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_coverage_ui_reads_plan_quality_and_runtime_evidence_without_mutation() -> None:
    source = _source(COVERAGE_SCRIPT)
    required = [
        "/settings/admin/evaluation-grants/coverage-plan",
        "/settings/admin/evaluation-grants/coverage-status",
        "/settings/admin/evaluation-grants/quality-status",
        "/settings/admin/evaluation-grants/task-quality-status",
        "Complete Endpoint Evaluation Coverage",
        "Declared coverage:",
        "Measured protected runtime coverage:",
        "Repeatability / endpoint quality evidence:",
        "Semantic task quality:",
        "public_availability_probe",
        "evaluation_key_runtime",
        "Campaign Client ID",
        "protected_runtime_coverage_complete",
        "quality_gate_passed",
        "P95",
        "multiple external programs",
    ]
    for marker in required:
        assert marker in source

    assert "method: 'GET'" in source
    assert "method: 'POST'" not in source
    assert "method: 'DELETE'" not in source
    assert "issue-key" not in source
    assert "api_key" not in source.lower().replace("api-key", "")
    assert "localStorage.setItem" not in source
    assert "sessionStorage.setItem" not in source


def test_coverage_ui_correlates_bounded_keys_by_campaign_client_id() -> None:
    source = _source(COVERAGE_SCRIPT)
    assert "function campaignClientId()" in source
    assert "admin-eval-client-id" in source
    assert "?client_id=${encodeURIComponent(clientId)}" in source
    assert "No single all-powerful key is required." in source
    assert "evidence is aggregated across bounded grants/keys" in source


def test_coverage_ui_does_not_count_public_health_as_api_key_proof() -> None:
    source = _source(COVERAGE_SCRIPT)
    assert "publicRows" in source
    assert "/health/live and /health/ready" in source
    assert "public reachability must not be misreported as key authorization evidence" in source


def test_coverage_ui_shows_repeatability_and_failure_quality_thresholds() -> None:
    source = _source(COVERAGE_SCRIPT)
    assert "quality_sufficient_endpoint_count" in source
    assert "min_successes_per_endpoint" in source
    assert "max_failure_rate" in source
    assert "p95_latency_ms" in source
    assert "quality_evidence_sufficient" in source
    assert "A P95 latency limit is evaluated only when explicitly supplied" in source


def test_admin_session_preloads_coverage_asset_but_authority_controls_hydration() -> None:
    session = _source(SESSION_SCRIPT)
    coverage = _source(COVERAGE_SCRIPT)

    assert "admin_evaluation_coverage.js?v=adminevalcoverage01" in session
    assert "loadEvaluationCoverageControls();" in session
    preload = session.rindex("loadEvaluationCoverageControls();")
    initial_check = session.rindex("checkAdminSession();")
    assert preload < initial_check

    assert "window.addEventListener('pmk-admin-session-verified', hydrate)" in coverage
    assert "if (!authorized()) return;" in coverage
    assert "document.body.dataset.adminEvaluationGrants === 'authorized'" in coverage


def test_coverage_ui_refreshes_after_grant_lifecycle_changes() -> None:
    source = _source(COVERAGE_SCRIPT)
    assert "pmk-evaluation-grant-updated" in source
    assert "loadStatus" in source
    assert "pmk-api-key-access-selection-changed" in source
