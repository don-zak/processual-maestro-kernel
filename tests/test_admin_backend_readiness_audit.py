from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "reports" / "ADMIN_BACKEND_READINESS_AUDIT.md"


def _audit_text() -> str:
    assert AUDIT.exists(), "ADMIN_BACKEND_READINESS_AUDIT.md must exist"
    return AUDIT.read_text(encoding="utf-8")


def test_admin_backend_readiness_audit_declares_phase_and_rules():
    text = _audit_text()

    assert "ADMIN-REVIEW-01" in text
    assert "No fake data" in text
    assert "Not wired yet" in text
    assert "planned" in text
    assert "wired" in text
    assert "placeholder" in text


def test_admin_backend_readiness_audit_covers_required_pages():
    text = _audit_text()

    required_pages = [
        "Admin Home",
        "Adapters",
        "API Keys",
        "Clients",
        "Usage Monitor",
        "Program Progress",
        "System Health",
        "System Settings",
    ]

    for page in required_pages:
        assert page in text


def test_admin_backend_readiness_audit_declares_specialized_admin_roles():
    text = _audit_text()

    required_roles = [
        "owner_admin",
        "ops_admin",
        "billing_admin",
        "support_admin",
        "security_admin",
        "viewer_admin",
    ]

    for role in required_roles:
        assert role in text


def test_admin_backend_readiness_audit_maps_security_scopes():
    text = _audit_text()

    required_scopes = [
        "admin:read",
        "admin:settings",
        "admin:api_keys:read",
        "admin:api_keys:write",
        "admin:api_keys:revoke",
        "admin:adapters:read",
        "admin:adapters:write",
        "admin:usage:read",
        "admin:clients:read",
        "admin:billing:read",
        "admin:health:read",
        "admin:audit:read",
        "admin:dangerous",
    ]

    for scope in required_scopes:
        assert scope in text


def test_admin_backend_readiness_audit_maps_known_wired_and_planned_endpoints():
    text = _audit_text()

    wired_endpoints = [
        "/auth/me",
        "/health/live",
        "/health/ready",
        "/adapters/status",
        "/settings/api-keys",
        "/applications",
    ]

    planned_endpoints = [
        "/settings/usage-logs",
        "/billing/events",
        "/billing/subscriptions",
        "/billing/plans",
    ]

    for endpoint in wired_endpoints:
        assert endpoint in text

    for endpoint in planned_endpoints:
        assert endpoint in text


def test_admin_backend_readiness_audit_separates_review_from_rbac_implementation():
    text = _audit_text()

    assert "It should not implement RBAC enforcement yet." in text
    assert "ADMIN-RBAC-01" in text
    assert "UI hiding is not security" in text
