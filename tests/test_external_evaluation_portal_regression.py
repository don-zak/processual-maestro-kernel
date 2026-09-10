from pathlib import Path


PORTAL = Path("processual_api/static/evaluation.html")
PORTAL_JS = Path("processual_api/static/js/evaluation_client_portal.js")
AUTH_JS = Path("processual_api/static/js/auth.js")


def test_external_evaluation_portal_has_no_demo_task_defaults() -> None:
    source = PORTAL.read_text(encoding="utf-8")

    assert "External Evaluation Workspace" in source
    assert "PostgreSQL-backed" in source
    assert "Production execution: disabled" in source
    assert "Subscription-free, grant-bounded sandbox evaluation" in source
    assert "demo-customer" not in source
    assert "evaluation.crm.integration" not in source
    assert '<textarea id="task-input" spellcheck="false">{}</textarea>' in source


def test_external_evaluation_portal_preserves_runtime_contract_ids() -> None:
    source = PORTAL.read_text(encoding="utf-8")
    required_ids = {
        "api-key",
        "connect",
        "disconnect",
        "message",
        "credential",
        "type",
        "quota-used",
        "quota-remaining",
        "grant-id",
        "key-id",
        "expires-at",
        "quota-bar",
        "quota-caption",
        "allowed-tasks",
        "allowed-bindings",
        "stage-admitted",
        "stage-executing",
        "stage-outcome",
        "stage-evidence",
        "execution-state",
        "execution-meta",
        "evidence-state",
        "evidence-meta",
        "quota-effect",
        "quota-effect-meta",
        "task-id",
        "binding-id",
        "idempotency-key",
        "task-input",
        "execute",
        "result",
        "customer-report",
    }
    for element_id in required_ids:
        assert f'id="{element_id}"' in source

    portal_js = PORTAL_JS.read_text(encoding="utf-8")
    assert "sessionStorage" not in portal_js
    assert "localStorage" not in portal_js
    assert "let apiKey = ''" in portal_js


def test_external_evaluation_portal_exposes_safe_authoritative_scope_and_progress() -> None:
    html = PORTAL.read_text(encoding="utf-8")
    js = PORTAL_JS.read_text(encoding="utf-8")

    for marker in (
        "Evaluation identity",
        "Authorized scope",
        "Execution progress",
        "Customer evaluation receipt",
        "Admitted",
        "Executing",
        "Evidence persisted",
        "Subscription</strong><span>No subscription",
    ):
        assert marker in html

    for marker in (
        "payload.grant_id",
        "payload.api_key_id",
        "payload.api_key_prefix",
        "payload.expires_at",
        "payload.allowed_task_ids",
        "payload.allowed_binding_ids",
        "external_evaluation_customer_receipt",
        "idempotent_replay",
        "Status refresh: +0 quota.",
        "New execution admitted; one evaluation quota unit consumed.",
        "raw_api_key_included: false",
        "raw_task_input_included: false",
        "qualification_decision: 'operator_controlled'",
    ):
        assert marker in js


def test_external_evaluation_portal_never_persists_or_reports_raw_key() -> None:
    js = PORTAL_JS.read_text(encoding="utf-8")

    assert "sessionStorage" not in js
    assert "localStorage" not in js
    assert "raw_api_key_included: false" in js
    assert "raw_task_input_included: false" in js
    assert "raw_secret" not in js.lower()


def test_client_console_badge_is_readiness_derived_not_demo_state() -> None:
    source = AUTH_JS.read_text(encoding="utf-8")

    assert "bootstrapClientReadinessBadge" in source
    assert "fetch('/health/ready'" in source
    assert "Operational readiness verified" in source
    assert "Readiness checks incomplete" in source
    assert "Readiness unavailable" in source
    assert "Derived from /health/ready" in source
