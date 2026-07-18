from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_runtime_loads_layout_cleanup_after_runtime():
    html = (STATIC_DIR / "admin.html").read_text(encoding="utf-8")

    assert "/console/js/admin_layout_cleanup.js" in html
    assert html.index("admin_runtime.js") < html.index("admin_layout_cleanup.js")


def test_admin_layout_cleanup_cleans_stacked_home_placeholders():
    cleanup = (STATIC_DIR / "js" / "admin_layout_cleanup.js").read_text(encoding="utf-8")

    required = [
        "pruneLegacyPlaceholders",
        "Checking admin session",
        "Planned usage view",
        "Planned supervisor controls",
        "data-admin-runtime-grid",
        "admin-page:not(.active)",
        "PMK_ADMIN_LAYOUT",
    ]

    for token in required:
        assert token in cleanup
