from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CGT_ROUTER_PATH = ROOT / "processual_api" / "routers" / "cgt_governor.py"
SETTINGS_ROUTER_PATH = ROOT / "processual_api" / "routers" / "settings.py"
SECURITY_PATH = ROOT / "processual_api" / "auth" / "security.py"

CGT_SOURCE = CGT_ROUTER_PATH.read_text(encoding="utf-8")
SETTINGS_SOURCE = SETTINGS_ROUTER_PATH.read_text(encoding="utf-8")
SECURITY_SOURCE = SECURITY_PATH.read_text(encoding="utf-8")


def _function_block(source: str, function_name: str) -> str:
    marker = f"async def {function_name}"
    start = source.index(marker)
    next_route = source.find("\n@router.", start + len(marker))
    if next_route == -1:
        return source[start:]
    return source[start:next_route]


def test_adapter_routes_keep_expected_scope_boundaries():
    expectations = [
        (
            CGT_SOURCE,
            '@router.get("/adapters/status")',
            "adapters_status",
            'Depends(require_scope("read:adapters"))',
        ),
        (
            CGT_SOURCE,
            '@router.post("/adapters/configure")',
            "configure_adapter",
            'Depends(require_scope("admin:settings"))',
        ),
        (
            CGT_SOURCE,
            '@router.get("/adapters/readiness")',
            "adapters_readiness",
            'Depends(require_scope("admin:settings"))',
        ),
        (
            CGT_SOURCE,
            '@router.post("/adapters/test")',
            "test_adapter",
            'Depends(require_scope("admin:settings"))',
        ),
    ]

    for source, route_marker, function_name, required_scope in expectations:
        assert route_marker in source
        assert required_scope in _function_block(source, function_name)


def test_sensitive_adapter_routes_do_not_fall_back_to_user_only_auth():
    for function_name in [
        "configure_adapter",
        "adapters_readiness",
        "test_adapter",
    ]:
        block = _function_block(CGT_SOURCE, function_name)

        assert "Depends(get_current_user)" not in block
        assert 'Depends(require_scope("admin:settings"))' in block


def test_settings_admin_routes_keep_admin_settings_scope():
    expectations = [
        ('@router.get("/plans"', "list_plans"),
        ('@router.get("/api-keys"', "list_api_keys"),
        ('@router.post("/api-keys"', "create_api_key"),
        ('@router.patch("/api-keys/{key_id}/plan"', "update_api_key_plan"),
        ('@router.patch("/api-keys/{key_id}/quota"', "update_api_key_quota"),
        ('@router.delete("/api-keys/{key_id}"', "delete_api_key"),
    ]

    for route_marker, function_name in expectations:
        assert route_marker in SETTINGS_SOURCE
        assert "Depends(require_scope(ADMIN_SETTINGS_SCOPE))" in _function_block(
            SETTINGS_SOURCE,
            function_name,
        )


def test_security_layer_declares_scope_enforcement_failure():
    assert "def require_scope" in SECURITY_SOURCE
    assert "Missing required scope" in SECURITY_SOURCE
