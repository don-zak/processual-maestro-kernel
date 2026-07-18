from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_console_no_longer_exposes_adapter_manager_admin_controls():
    html = read_static("index.html")

    forbidden = [
        'data-page="adapters"',
        'id="page-adapters"',
        "Adapter Manager",
        "Configure Provider",
        "Test Connection",
        "adp-configure-btn",
        "adp-test-btn",
        "/adapters/configure",
        "/adapters/test",
        'js/adapters/adapters.js',
        'js/pages/adapters.js',
    ]

    for token in forbidden:
        assert token not in html


def test_admin_exposes_adapter_manager_admin_controls():
    html = read_static("admin.html")

    required = [
        "Adapters",
        "Adapter Manager",
        "Configure Provider",
        "Test Connection",
        "adp-configure-btn",
        "adp-test-btn",
        'js/adapters/adapters.js',
        'js/admin_adapters.js',
    ]

    for token in required:
        assert token in html


def test_admin_dedicated_adapter_script_uses_existing_backend_adapter_client():
    script = (STATIC_DIR / "js" / "admin_adapters.js").read_text(encoding="utf-8")

    required = [
        "ADAPTERS_ADAPTER.status",
        "ADAPTERS_ADAPTER.configure",
        "ADAPTERS_ADAPTER.test",
    ]

    for token in required:
        assert token in script
