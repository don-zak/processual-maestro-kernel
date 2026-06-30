from pathlib import Path

ROUTER_PATH = (
    Path(__file__).resolve().parents[1]
    / "processual_api"
    / "routers"
    / "cgt_governor.py"
)

SOURCE = ROUTER_PATH.read_text(encoding="utf-8")


def _function_block(function_name: str) -> str:
    marker = f"async def {function_name}"
    start = SOURCE.index(marker)
    next_route = SOURCE.find("\n@router.", start + len(marker))
    if next_route == -1:
        return SOURCE[start:]
    return SOURCE[start:next_route]


def test_adapters_readiness_route_requires_admin_settings_scope():
    assert '@router.get("/adapters/readiness")' in SOURCE

    block = _function_block("adapters_readiness")

    assert 'Depends(require_scope("admin:settings"))' in block
    assert "adapter_registry.all().items()" in block
    assert "provider_public_metadata(name)" in block
    assert "await adapter.is_available()" in block
    assert "adapter.is_configured()" in block


def test_adapters_readiness_response_shape_is_regression_protected():
    block = _function_block("adapters_readiness")

    for field in [
        '"providers"',
        '"total"',
        '"configured_count"',
        '"ok_count"',
        '"default"',
    ]:
        assert field in block

    for provider_field in [
        "**metadata",
        '"provider"',
        '"name"',
        '"configured"',
        '"ok"',
        '"latency_ms"',
        '"model"',
        '"message"',
    ]:
        assert provider_field in block


def test_adapter_status_and_test_scopes_remain_protected():
    status_block = _function_block("adapters_status")
    test_block = _function_block("test_adapter")

    assert '@router.get("/adapters/status")' in SOURCE
    assert 'Depends(require_scope("read:adapters"))' in status_block

    assert '@router.post("/adapters/test")' in SOURCE
    assert 'Depends(require_scope("admin:settings"))' in test_block
