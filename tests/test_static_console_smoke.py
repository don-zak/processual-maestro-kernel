import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "processual_api" / "static"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_static_console_core_files_exist():
    required_paths = [
        STATIC_ROOT,
        STATIC_ROOT / "index.html",
        STATIC_ROOT / "login.html",
        STATIC_ROOT / "splash.html",
        STATIC_ROOT / "favicon.svg",
        STATIC_ROOT / "css" / "console.css",
        STATIC_ROOT / "css" / "tour.css",
        STATIC_ROOT / "js" / "app.js",
        STATIC_ROOT / "js" / "auth.js",
        STATIC_ROOT / "js" / "charts.js",
        STATIC_ROOT / "js" / "client.js",
        STATIC_ROOT / "js" / "i18n.js",
        STATIC_ROOT / "js" / "adapters",
        STATIC_ROOT / "js" / "pages",
        STATIC_ROOT / "js" / "tour",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    assert not missing, f"Missing static console core files: {missing}"


def test_static_console_page_modules_exist():
    required_pages = [
        "overview.js",
        "cgt.js",
        "workflows.js",
        "governance.js",
        "telemetry.js",
        "reports.js",
        "governor.js",
        "gateway.js",
        "simulation.js",
        "adapters.js",
        "settings.js",
    ]

    missing = [
        name for name in required_pages
        if not (STATIC_ROOT / "js" / "pages" / name).is_file()
    ]
    assert not missing, f"Missing static console page modules: {missing}"


def test_static_console_api_adapter_modules_exist():
    required_adapters = [
        "adapters.js",
        "cgt.js",
        "gateway.js",
        "governance.js",
        "governor.js",
        "health.js",
        "reports.js",
        "simulation.js",
        "telemetry.js",
        "workflows.js",
    ]

    missing = [
        name for name in required_adapters
        if not (STATIC_ROOT / "js" / "adapters" / name).is_file()
    ]
    assert not missing, f"Missing static console API adapter modules: {missing}"


def test_static_console_tour_files_exist():
    required_tour_files = [
        STATIC_ROOT / "js" / "tour" / "tour-engine.js",
        STATIC_ROOT / "js" / "tour" / "tour-steps.js",
        STATIC_ROOT / "css" / "tour.css",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required_tour_files if not path.is_file()]
    assert not missing, f"Missing static console tour files: {missing}"


def test_main_serves_static_console_login_and_splash_pages():
    source = read_text(ROOT / "processual_api" / "main.py")

    required_markers = [
        "from fastapi.responses import HTMLResponse",
        "from fastapi.staticfiles import StaticFiles",
        '_static_dir = Path(__file__).resolve().parent / "static"',
        'app.mount("/console", StaticFiles(directory=str(_static_dir), html=True), name="console")',
        'static" / "splash.html"',
        'static" / "login.html"',
        "async def splash_page(",
        '@app.get("/login", response_class=HTMLResponse',
        "async def login_page(",
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing main.py static serving markers: {missing}"


def test_static_console_app_shell_keeps_navigation_and_subscription_markers():
    source = read_text(STATIC_ROOT / "js" / "app.js")

    required_markers = [
        "overview",
        "cgt",
        "workflows",
        "governance",
        "telemetry",
        "reports",
        "governor",
        "gateway",
        "simulation",
        "adapters",
        "settings",
        "checkSubscription",
        "CLIENT.get('/settings/subscription')",
        "/billing/portal",
        "/login",
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing app shell markers: {missing}"


def test_static_console_client_and_auth_keep_fetch_and_login_markers():
    client_source = read_text(STATIC_ROOT / "js" / "client.js")
    auth_source = read_text(STATIC_ROOT / "js" / "auth.js")

    client_markers = [
        "async function fetchJSON",
        "fetch(BASE + path, opts)",
        "get:",
        "post:",
        "put:",
        "del:",
    ]

    auth_markers = [
        "async function login",
        "logout",
        "isLoggedIn",
        "currentUser",
        "me",
    ]

    missing_client = [marker for marker in client_markers if marker not in client_source]
    missing_auth = [marker for marker in auth_markers if marker not in auth_source]

    assert not missing_client, f"Missing client.js markers: {missing_client}"
    assert not missing_auth, f"Missing auth.js markers: {missing_auth}"


def test_static_console_settings_and_adapter_pages_keep_api_markers():
    settings_source = read_text(STATIC_ROOT / "js" / "pages" / "settings.js")
    adapters_source = read_text(STATIC_ROOT / "js" / "pages" / "adapters.js")
    adapter_api_source = read_text(STATIC_ROOT / "js" / "adapters" / "adapters.js")

    settings_markers = [
        "settings",
        "api",
        "key",
        "subscription",
    ]

    adapters_markers = [
        "adapters",
        "provider",
        "model",
    ]

    adapter_api_markers = [
        "adapters",
    ]

    missing_settings = [
        marker for marker in settings_markers
        if marker.lower() not in settings_source.lower()
    ]
    missing_adapters = [
        marker for marker in adapters_markers
        if marker.lower() not in adapters_source.lower()
    ]
    missing_adapter_api = [
        marker for marker in adapter_api_markers
        if marker.lower() not in adapter_api_source.lower()
    ]

    assert not missing_settings, f"Missing settings page markers: {missing_settings}"
    assert not missing_adapters, f"Missing adapters page markers: {missing_adapters}"
    assert not missing_adapter_api, f"Missing adapter API markers: {missing_adapter_api}"


def test_static_html_local_asset_references_exist():
    html_files = [
        STATIC_ROOT / "index.html",
        STATIC_ROOT / "login.html",
        STATIC_ROOT / "splash.html",
    ]

    missing_assets = []

    for html_file in html_files:
        html = read_text(html_file)
        refs = re.findall(r'''(?:src|href)=["']([^"']+)["']''', html)

        for ref in refs:
            if not ref or ref.startswith(("http://", "https://", "data:", "#", "mailto:")):
                continue

            clean = ref.split("?", 1)[0].split("#", 1)[0]
            if clean.startswith("/console/"):
                candidate = STATIC_ROOT / clean.removeprefix("/console/")
            elif clean.startswith("/"):
                continue
            else:
                candidate = html_file.parent / clean

            if not candidate.exists():
                missing_assets.append(
                    f"{html_file.relative_to(ROOT)} -> {ref}"
                )

    assert not missing_assets, f"Missing local static asset references: {missing_assets}"