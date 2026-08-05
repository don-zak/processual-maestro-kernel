from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"


def test_home_layout_removes_duplicate_supervisor_navigation_card() -> None:
    source = (STATIC / "js" / "admin_home_layout.js").read_text(encoding="utf-8")
    assert "admin-supervisor-home-console" in source
    assert "Supervisor Operations Center" in source
    assert "card.remove()" in source


def test_api_key_summary_is_visibility_only() -> None:
    summary = (STATIC / "js" / "admin_api_key_summary.js").read_text(encoding="utf-8")
    management = (STATIC / "js" / "admin_api_keys.js").read_text(encoding="utf-8")

    assert "method: 'GET'" in summary
    assert "method: 'POST'" not in summary
    assert "method: 'PUT'" not in summary
    assert "method: 'PATCH'" not in summary
    assert "method: 'DELETE'" not in summary

    assert "POST" in management or "PUT" in management or "DELETE" in management


def test_home_contains_no_independent_api_key_mutation_form() -> None:
    html = (STATIC / "admin.html").read_text(encoding="utf-8")
    home_start = html.index('id="page-admin-home"')
    marketplace_start = html.index('id="page-admin-marketplace"')
    home = html[home_start:marketplace_start]

    assert "admin-api-key-create" not in home
    assert "admin-api-key-revoke" not in home
    assert "admin-api-key-rotate" not in home
