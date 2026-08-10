from pathlib import Path

SUPERVISOR_STATS = Path("processual_api/static/js/admin_supervisor_stats.js")
CLIENT_REQUESTS = Path("processual_api/static/js/admin_client_requests.js")


def test_supervisor_overview_does_not_recreate_navigation_console() -> None:
    source = SUPERVISOR_STATS.read_text(encoding="utf-8")

    assert "Supervisor Overview" in source
    assert "visibility only" in source
    assert "admin-supervisor-home-console" not in source
    assert "Supervisor Operations Center" not in source
    assert "ensureSupervisorHomeConsole" not in source


def test_supervisor_overview_is_read_only() -> None:
    source = SUPERVISOR_STATS.read_text(encoding="utf-8")

    assert "method: 'GET'" in source
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert f"method: '{method}'" not in source
        assert f'method: "{method}"' not in source


def test_client_request_mutations_remain_in_clients_module() -> None:
    source = CLIENT_REQUESTS.read_text(encoding="utf-8")

    assert "/settings/admin/client-requests" in source
    assert "response-draft" in source
    assert "supervisor-response" in source
    assert "case-item-action" in source
    assert "fetch(" in source


def test_overview_declares_clients_page_ownership() -> None:
    source = SUPERVISOR_STATS.read_text(encoding="utf-8")

    assert "Actions remain owned by the Clients page" in source
    assert "PMK_ADMIN_SUPERVISOR_STATS" in source
    assert "pmk-client-request-updated" in source
