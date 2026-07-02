
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_layout_cleanup_removes_protected_area_and_forces_scroll():
    script = (STATIC_DIR / "js" / "admin_layout_cleanup.js").read_text(encoding="utf-8")

    required = [
        "PROTECTED AREA",
        "Protected Area",
        "Admin auth token missing",
        "data-admin-runtime-grid",
        "height:calc(100vh - 76px)",
        "overflow:auto",
        "setTimeout(clean, 2500)",
        "PMK_ADMIN_LAYOUT",
    ]

    for token in required:
        assert token in script
