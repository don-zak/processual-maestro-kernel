from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_grant_archive.py"
ROUTE_REGISTRY = ROOT / "processual_api" / "routers" / "external_evaluation_route_registry.py"
DOM_CONTRACT = ROOT / "processual_api" / "static" / "js" / "admin_external_evaluation_dom_contract.js"
ARCHIVE_UI = ROOT / "processual_api" / "static" / "js" / "admin_evaluation_grant_archive.js"


def test_archive_is_soft_delete_and_revokes_authority_first() -> None:
    source = ARCHIVE_ROUTER.read_text(encoding="utf-8")
    assert "revoke_evaluation_authority_grant" in source
    assert 'grant["archived_at"] = now' in source
    assert '"historical_audit_preserved": True' in source
    assert "del " not in source
    assert "hard delete" in source.lower()


def test_default_admin_list_omits_archived_grants() -> None:
    source = ARCHIVE_ROUTER.read_text(encoding="utf-8")
    assert 'if grant.get("archived_at"):' in source
    assert '"archive_semantics": "soft_delete_preserves_audit"' in source
    registry = ROUTE_REGISTRY.read_text(encoding="utf-8")
    assert "list_visible_evaluation_grants" in registry
    assert "archive_evaluation_grant" in registry
    assert '"/settings/admin/evaluation-grants/{grant_id}/archive"' in registry


def test_admin_loads_per_grant_delete_control() -> None:
    dom = DOM_CONTRACT.read_text(encoding="utf-8")
    ui = ARCHIVE_UI.read_text(encoding="utf-8")
    assert "admin_evaluation_grant_archive.js?v=eval-grant-archive-v1" in dom
    assert "data-eval-archive" in ui
    assert "Delete Grant" in ui
    assert "/archive" in ui
    assert "historical audit evidence" in ui.lower()
    assert "window.confirm" in ui


def test_delete_control_preserves_security_boundaries() -> None:
    ui = ARCHIVE_UI.read_text(encoding="utf-8")
    router = ARCHIVE_ROUTER.read_text(encoding="utf-8")
    assert "credentials: 'include'" in ui
    assert "require_active_platform_admin" in router
    assert '"production_allowed": False' in router
    assert "raw" not in ui.lower().replace("raw = await response.text()", "")
