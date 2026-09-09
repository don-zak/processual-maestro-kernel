from pathlib import Path


PORTAL = Path("processual_api/static/evaluation.html")
PORTAL_JS = Path("processual_api/static/js/evaluation_client_portal.js")
AUTH_JS = Path("processual_api/static/js/auth.js")


def test_external_evaluation_portal_has_no_demo_task_defaults() -> None:
    source = PORTAL.read_text(encoding="utf-8")

    assert "External Evaluation Workspace" in source
    assert "PostgreSQL-backed" in source
    assert "Production execution: disabled" in source
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
        "quota-bar",
        "quota-caption",
        "execution-state",
        "execution-meta",
        "evidence-state",
        "evidence-meta",
        "task-id",
        "binding-id",
        "idempotency-key",
        "task-input",
        "execute",
        "result",
    }
    for element_id in required_ids:
        assert f'id="{element_id}"' in source

    portal_js = PORTAL_JS.read_text(encoding="utf-8")
    assert "sessionStorage" not in portal_js
    assert "localStorage" not in portal_js
    assert "let apiKey = ''" in portal_js


def test_client_console_badge_is_readiness_derived_not_demo_state() -> None:
    source = AUTH_JS.read_text(encoding="utf-8")

    assert "bootstrapClientReadinessBadge" in source
    assert "fetch('/health/ready'" in source
    assert "Operational readiness verified" in source
    assert "Readiness checks incomplete" in source
    assert "Readiness unavailable" in source
    assert "Derived from /health/ready" in source
