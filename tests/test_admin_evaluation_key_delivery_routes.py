from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "processual_api" / "routers" / "external_evaluation_route_registry.py"
ROUTER = ROOT / "processual_api" / "routers" / "settings_admin_evaluation_key_lifecycle.py"


def test_external_evaluation_registry_exposes_individual_key_lifecycle_routes() -> None:
    source = REGISTRY.read_text(encoding="utf-8")

    required = [
        "list_evaluation_keys",
        "confirm_evaluation_key_delivery",
        "acknowledge_evaluation_key_receipt",
        "revoke_evaluation_key",
        '"/settings/admin/evaluation-grants/{grant_id}/keys"',
        '"/settings/admin/evaluation-grants/{grant_id}/keys/{key_id}/confirm-delivery"',
        '"/settings/admin/evaluation-grants/{grant_id}/keys/{key_id}/acknowledge"',
        '"/settings/admin/evaluation-grants/{grant_id}/keys/{key_id}"',
    ]
    for marker in required:
        assert marker in source


def test_key_lifecycle_router_keeps_platform_admin_authority_and_no_raw_secret_endpoint() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert "require_active_platform_admin" in source
    assert "raw_secret_visible" in source
    assert '"raw_secret_visible": False' in source
    assert "confirm_delivery" in source
    assert "acknowledge" in source
    assert "revoke" in source
    assert "api_key" not in source.split("return {\"status\": \"ready\"")[1].split("}", 1)[0]
