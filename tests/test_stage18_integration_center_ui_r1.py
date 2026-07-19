# ruff: noqa

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_stage18_admin_integration_center_is_wired_to_existing_safe_routes():
    nav = _text("processual_api/static/js/admin_nav.js")
    center = _text("processual_api/static/js/admin_integration_center_18.js")

    assert "integration-center" in nav
    assert "admin-integration-center-root" in nav
    assert "/settings/admin/integration-readiness-tracking/cases" in center
    assert "/settings/admin/operator-pilot-handoff" in center
    assert "/settings/admin/operator-pilot-handoff/progress" in center
    assert "Production" in center
    assert "NO-GO" in center
    assert "No raw secrets" in center
    assert "Secrets operations" in center
    assert "Restart persistence" in center
    assert "Encrypted backup and restore" in center


def test_stage18_client_institution_workspace_is_a_safe_projection():
    app = _text("processual_api/static/js/app.js")
    workspace = _text("processual_api/static/js/pages/institution_workspace_18.js")

    assert 'data-page="institution"' in app
    assert "institution-workspace-root" in app
    assert "/settings/client/integration-readiness" in workspace
    assert "/settings/client/requests" in workspace
    assert "Credential values are never displayed here" in workspace
    assert "Production blocked" in workspace


def test_stage18_new_ui_does_not_embed_secret_material():
    combined = "\n".join(
        [
            _text("processual_api/static/js/admin_integration_center_18.js"),
            _text("processual_api/static/js/pages/institution_workspace_18.js"),
        ]
    ).lower()

    forbidden = (
        "client_secret=",
        "access_token=",
        "authorization: bearer ",
        "sk-",
        "private_key=",
        "password=",
    )
    for marker in forbidden:
        assert marker not in combined
