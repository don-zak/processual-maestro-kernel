from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_loads_dashboard_script():
    html = read_static("admin.html")
    assert "js/admin_dashboard.js" in html


def test_admin_dashboard_uses_real_backend_endpoints():
    script = (STATIC_DIR / "js" / "admin_dashboard.js").read_text(encoding="utf-8")

    required = [
        "safeGet('/auth/me')",
        "safeGet('/health/live')",
        "safeGet('/health/ready')",
        "safeGet('/adapters/status')",
        "safeGet('/settings/api-keys')",
        "safeGet('/applications')",
        "safeGet('/billing/events')",
        "safeGet('/billing/subscriptions')",
        "safeGet('/settings/usage-logs')",
    ]

    for token in required:
        assert token in script


def test_admin_dashboard_contains_tables_and_charts_for_supervisor_cards():
    script = (STATIC_DIR / "js" / "admin_dashboard.js").read_text(encoding="utf-8")

    required = [
        "admin-data-table",
        "admin-bar-chart",
        "Admin Session",
        "System Health",
        "Provider Status",
        "API Keys Registry",
        "Clients, Applications, Subscriptions",
        "Usage Monitor",
        "Program Progress",
        "Not wired yet",
        "PMK_ADMIN_DASHBOARD",
    ]

    for token in required:
        assert token in script
