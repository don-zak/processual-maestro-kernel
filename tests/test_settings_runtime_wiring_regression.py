from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_settings_backend_router_remains_wired_into_main() -> None:
    main = _read(ROOT / "processual_api" / "main.py")

    assert "from .routers import settings as settings_router" in main
    assert "app.include_router(settings_router.router)" in main


def test_current_settings_ui_assets_remain_wired() -> None:
    index = _read(STATIC / "index.html")
    app = _read(STATIC / "js" / "app.js")

    assert "js/pages/settings.js" in index
    assert "css/settings_operations_18.css" in app
    assert "js/settings_operations_18.js" in app
    assert "css/settings_layout_18.css" in app
    assert "js/settings_layout_18.js" in app
    assert "window.PMK_SETTINGS_OPERATIONS_18?.init?.()" in app
    assert "window.PMK_SETTINGS_LAYOUT_18?.init?.()" in app


def test_current_client_settings_ui_uses_replacement_provider_routes() -> None:
    settings_js = _read(STATIC / "js" / "pages" / "settings.js")

    assert "/settings/provider-connection" in settings_js
    assert "/settings/provider-connection/setup" in settings_js
    assert "/settings/provider-connection/test" in settings_js
    assert "/settings/llm-provider" not in settings_js


def test_operations_center_reuses_primary_provider_status_without_duplicate_get() -> None:
    operations_js = _read(STATIC / "js" / "settings_operations_18.js")

    assert "providerSnapshotFromPage" in operations_js
    assert "observeProviderStatus" in operations_js
    assert "new MutationObserver(syncProviderFromPage)" in operations_js
    assert "CLIENT.get('/settings/client/provider-connection')" not in operations_js
    assert "CLIENT.get('/settings/provider-connection')" not in operations_js


def test_current_client_settings_ui_uses_client_scoped_usage_summary() -> None:
    settings_js = _read(STATIC / "js" / "pages" / "settings.js")

    assert "/settings/client/usage-summary" in settings_js
    assert "CLIENT.get('/settings/usage-summary')" not in settings_js


def test_settings_retirement_candidates_still_exist_until_explicit_removal() -> None:
    router = _read(ROOT / "processual_api" / "routers" / "settings.py")

    assert '@router.put("/llm-provider"' in router
    assert '@router.delete("/llm-provider"' in router
    assert '@router.post("/llm-provider/test"' in router
    assert '@router.get("/usage-summary"' in router


def test_top_up_checkout_contract_is_not_dead_code() -> None:
    application_service = _read(
        ROOT / "processual_api" / "billing" / "commercial_top_up_application_service.py"
    )

    assert "commercial_settings_top_up_checkout_contracts" in application_service
    assert "TopUpCheckoutChannel" in application_service
