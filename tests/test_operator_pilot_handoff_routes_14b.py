from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "processual_api" / "main.py"
SERVICE = ROOT / "processual_api" / "services" / "operator_pilot_handoff.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_operator_pilot_handoff_14b_routes_are_registered() -> None:
    main = _read(MAIN)

    assert '@app.get("/settings/admin/operator-pilot-handoff")' in main
    assert '@app.get("/settings/admin/operator-pilot-handoff/export")' in main
    assert "admin_operator_pilot_handoff_package_14b" in main
    assert "admin_operator_pilot_handoff_export_14b" in main


def test_operator_pilot_handoff_14b_routes_follow_existing_read_only_admin_pattern() -> None:
    main = _read(MAIN)

    route_start = main.find("BEGIN INTEGRATION_ONBOARDING_14B_OPERATOR_PILOT_HANDOFF_ROUTES")
    route_end = main.find("END INTEGRATION_ONBOARDING_14B_OPERATOR_PILOT_HANDOFF_ROUTES")

    assert route_start >= 0
    assert route_end > route_start

    route_chunk = main[route_start:route_end]

    assert "def admin_operator_pilot_handoff_package_14b()" in route_chunk
    assert "def admin_operator_pilot_handoff_export_14b()" in route_chunk
    assert "PlainTextResponse" in route_chunk
    assert "require_admin" not in route_chunk
    assert "await request.json" not in route_chunk
    assert "@app.post" not in route_chunk


def test_operator_pilot_handoff_14b_routes_preserve_safety_contract() -> None:
    main = _read(MAIN)
    service = _read(SERVICE)
    combined = main + "\n" + service

    expected_markers = [
        "build_operator_pilot_handoff_package",
        "render_operator_pilot_handoff_markdown",
        "production_allowed",
        "runtime_connector_approved",
        "customer_credentials_present",
        "external_http_allowed",
    ]

    for marker in expected_markers:
        assert marker in combined

    forbidden_markers = [
        "production_allowed=True",
        "runtime_connector_approved=True",
        "customer_credentials_present=True",
        "external_http_allowed=True",
        "requests.",
        "httpx.",
        "urllib.request",
    ]

    for marker in forbidden_markers:
        assert marker not in combined


def test_operator_pilot_handoff_14b_export_is_markdown_attachment() -> None:
    main = _read(MAIN)

    export_start = main.find('"/settings/admin/operator-pilot-handoff/export"')
    assert export_start >= 0

    export_chunk = main[export_start : export_start + 1400]

    assert 'media_type="text/markdown; charset=utf-8"' in export_chunk
    assert "Content-Disposition" in export_chunk
    assert "operator-pilot-handoff-14b.md" in export_chunk


def test_operator_pilot_handoff_14b_does_not_add_runtime_connector_activation() -> None:
    main = _read(MAIN)

    route_start = main.find("BEGIN INTEGRATION_ONBOARDING_14B_OPERATOR_PILOT_HANDOFF_ROUTES")
    route_end = main.find("END INTEGRATION_ONBOARDING_14B_OPERATOR_PILOT_HANDOFF_ROUTES")
    assert route_start >= 0
    assert route_end > route_start

    route_chunk = main[route_start:route_end]
    lowered = route_chunk.lower()

    forbidden_route_markers = [
        "@app.post",
        "await request.json",
        "production_allowed=true",
        "runtime_connector_approved=true",
        "requests.",
        "httpx.",
        "urllib.request",
    ]

    for marker in forbidden_route_markers:
        assert marker not in lowered

def test_operator_pilot_handoff_14b_markdown_contains_machine_readable_guardrails() -> None:
    from processual_api.services.operator_pilot_handoff import (
        build_operator_pilot_handoff_package,
        render_operator_pilot_handoff_markdown,
    )

    markdown = render_operator_pilot_handoff_markdown(
        build_operator_pilot_handoff_package()
    )

    assert "## Machine-readable guardrail keys" in markdown
    assert "production_allowed: false" in markdown
    assert "runtime_connector_approved: false" in markdown
    assert "customer_credentials_present: false" in markdown
    assert "external_http_allowed: false" in markdown
