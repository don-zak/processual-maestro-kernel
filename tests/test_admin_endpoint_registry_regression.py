
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_runtime_classifies_planned_endpoints_without_fetching():
    script = (STATIC_DIR / "js" / "admin_runtime.js").read_text(encoding="utf-8")

    required = [
        "ADMIN_ENDPOINT_REGISTRY",
        "isPlannedOnlyEndpoint",
        "plannedEndpointResult",
        "/settings/usage-logs",
        "/billing/events",
        "/billing/subscriptions",
        "/billing/plans",
        "Not wired yet: backend route is planned but not implemented.",
        "PMK_ADMIN_ENDPOINT_REGISTRY",
    ]

    for token in required:
        assert token in script


def test_admin_uses_fresh_runtime_cache_bust():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "v=adminruntime05" in html
    assert "v=adminauthbridge02" not in html
    assert "v=adminhome04" not in html
