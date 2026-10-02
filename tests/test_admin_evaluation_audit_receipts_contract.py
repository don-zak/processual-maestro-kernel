from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "processual_api" / "services" / "evaluation_runtime_delivery_postgres.py"
ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_key_lifecycle.py"
REGISTRY = ROOT / "processual_api" / "routers" / "external_evaluation_route_registry.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_admin_audit_receipt_is_whitelisted_and_secret_safe() -> None:
    source = _read(SERVICE)

    assert "_AUDIT_EVIDENCE_KEYS" in source
    assert '"raw_task_input_persisted": False' in source
    assert '"raw_secret_visible": False' in source
    assert '"audit_copy_for_admin": True' in source
    assert "replay_response" not in source[source.index("def _audit_receipt"): source.index("async def list_evaluation_audit_receipts")]


def test_admin_audit_receipts_are_scoped_to_owner_and_grant() -> None:
    source = _read(SERVICE)

    assert "EvaluationRuntimeDelivery.owner_id_sha256 == _owner_digest(owner_id)" in source
    assert "EvaluationRuntimeDelivery.grant_id == grant_id" in source
    assert ".limit(bounded_limit)" in source


def test_admin_audit_route_requires_platform_admin() -> None:
    source = _read(ROUTER)

    assert '"/admin/evaluation-grants/{grant_id}/audit-receipts"' in source
    assert "await _require_platform_admin(request, current_user)" in source
    assert '"report_type": "external_evaluation_admin_audit"' in source
    assert '"raw_secret_visible": False' in source


def test_audit_route_is_registered_on_canonical_admin_surface() -> None:
    source = _read(REGISTRY)

    assert "list_evaluation_audit_report_receipts" in source
    assert '"/settings/admin/evaluation-grants/{grant_id}/audit-receipts"' in source
    assert '"/admin/evaluation-grants/{grant_id}/audit-receipts"' in source
