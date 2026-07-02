from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_console_does_not_expose_api_key_admin_controls():
    html = read_static("index.html")

    forbidden = [
        "Generate New Key",
        "admin-api-key-generate-btn",
        "admin-api-key-refresh-btn",
        "settings/api-keys",
        "API Keys",
    ]

    for token in forbidden:
        assert token not in html


def test_admin_exposes_api_key_admin_controls():
    html = read_static("admin.html")

    required = [
        "API Keys",
        "Generate New Key",
        "admin-api-key-generate-btn",
        "admin-api-key-refresh-btn",
        "js/admin_api_keys.js",
    ]

    for token in required:
        assert token in html


def test_admin_api_key_script_uses_admin_settings_api_key_endpoints():
    script = (STATIC_DIR / "js" / "admin_api_keys.js").read_text(encoding="utf-8")

    required = [
        "CLIENT.get('/settings/api-keys')",
        "CLIENT.post('/settings/api-keys'",
        "admin-api-key-generate-btn",
        "admin-api-key-refresh-btn",
    ]

    for token in required:
        assert token in script
