from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_loads_runtime_script_and_top_actions():
    html = read_static("admin.html")

    required = [
        "js/admin_runtime.js",
        "admin-client-console-btn",
        'href="/console"',
        "admin-logout-btn",
        'href="/login?mode=admin"',
    ]

    for token in required:
        assert token in html


def test_admin_runtime_binds_api_key_generation_and_refresh():
    script = (STATIC_DIR / "js" / "admin_runtime.js").read_text(encoding="utf-8")

    required = [
        "generateApiKey",
        "admin-api-key-generate-btn",
        "admin-api-key-refresh-btn",
        "safePost('/settings/api-keys'",
        "safePost('/settings/api-keys/generate'",
        "refreshApiKeys",
        "PMK_ADMIN_RUNTIME",
    ]

    for token in required:
        assert token in script


def test_admin_runtime_adds_tables_charts_and_backend_wiring():
    script = (STATIC_DIR / "js" / "admin_runtime.js").read_text(encoding="utf-8")

    required = [
        "admin-data-table",
        "admin-bar-chart",
        "safeGet('/auth/me')",
        "safeGet('/health/live')",
        "safeGet('/health/ready')",
        "safeGet('/adapters/status')",
        "safeGet('/settings/api-keys')",
        "safeGet('/settings/usage-logs')",
        "safeGet('/applications')",
        "safeGet('/billing/subscriptions')",
        "Not wired yet",
        "Operations Summary",
        "Provider Registry Table",
        "API Keys Registry Table",
        "Usage Monitor Table",
        "Readiness Checklist",
        "Health and Readiness Table",
    ]

    for token in required:
        assert token in script
