from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "processual_api" / "services" / "evaluation_runtime_delivery_postgres.py"
ROUTES = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_grants.py"


def test_runtime_summary_projection_excludes_sensitive_delivery_material() -> None:
    source = DELIVERY.read_text(encoding="utf-8")
    start = source.index("async def list_evaluation_execution_summaries")
    end = source.index("__all__", start)
    projection = source[start:end]

    required = [
        '"record_id"',
        '"grant_id"',
        '"api_key_id"',
        '"task_id"',
        '"binding_id"',
        '"state"',
        '"evaluation_stage"',
        '"maestro_task_completed"',
        '"next_readiness_stage"',
        '"governance_qualified"',
        '"governance_version"',
        '"governance_operation_id"',
        '"governance_fail_closed"',
        '"runtime_attested_at"',
        '"raw_task_input_persisted": False',
        '"raw_secret_visible": False',
    ]
    for marker in required:
        assert marker in projection

    assert '"request_fingerprint":' not in projection
    assert '"idempotency_key_sha256":' not in projection
    assert '"replay_response":' not in projection
    assert '"evidence": dict(' not in projection


def test_runtime_summary_route_is_platform_admin_visibility_only() -> None:
    source = ROUTES.read_text(encoding="utf-8")
    start = source.index("async def evaluation_runtime_summary")
    end = source.index("@settings_module.router.post", start)
    route = source[start:end]

    assert "await _require_platform_admin(request, current_user)" in route
    assert "list_evaluation_execution_summaries" in route
    assert '"visibility_only": True' in route
    assert '"raw_task_input_visible": False' in route
    assert '"raw_secret_visible": False' in route
    assert '"commercial_quota_required"' not in route
