from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"
ADMIN_HTML = STATIC_DIR / "admin.html"


def test_admin_uses_absolute_console_static_script_paths():
    html = ADMIN_HTML.read_text(encoding="utf-8")

    required = [
        'src="/console/js/client.js',
        'src="/console/js/adapters/adapters.js',
        'src="/console/js/admin_adapters.js',
        'src="/console/js/admin_api_keys.js',
        'src="/console/js/admin_nav.js',
        'src="/console/js/admin_session.js',
        'src="/console/js/admin_actions.js',
        'src="/console/js/admin_dashboard.js',
        'src="/console/js/admin_runtime.js',
    ]

    for token in required:
        assert token in html


def test_admin_does_not_use_relative_static_script_paths():
    html = ADMIN_HTML.read_text(encoding="utf-8")

    forbidden = [
        'src="js/client.js',
        'src="js/adapters/adapters.js',
        'src="js/admin_adapters.js',
        'src="js/admin_api_keys.js',
        'src="js/admin_nav.js',
        'src="js/admin_session.js',
        'src="js/admin_actions.js',
        'src="js/admin_dashboard.js',
        'src="js/admin_runtime.js',
    ]

    for token in forbidden:
        assert token not in html
