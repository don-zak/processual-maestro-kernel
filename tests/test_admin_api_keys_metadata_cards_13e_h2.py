import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"
ADMIN_API_KEYS_JS = ROOT / "processual_api" / "static" / "js" / "admin_api_keys.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_13e_h2_metadata_card_classes_are_present() -> None:
    source = read(ADMIN_API_KEYS_JS)

    assert "admin-supervisor-session-metadata-card" in source
    assert "admin-api-key-metadata-card" in source
    assert "admin-api-key-metadata-card-list" in source


def test_13e_h2_cards_are_collapsible_with_details_summary() -> None:
    source = read(ADMIN_API_KEYS_JS)

    assert "details" in source
    assert "summary" in source


def test_13e_h2_unsafe_raw_markers_are_not_present_as_visible_metadata_labels() -> None:
    source = read(ADMIN_API_KEYS_JS)

    forbidden_visible_patterns = [
        r">\s*raw_key\s*<",
        r">\s*key_hash\s*<",
        r">\s*raw_secret\s*<",
        r"""label\s*:\s*['"]raw_key['"]""",
        r"""label\s*:\s*['"]key_hash['"]""",
        r"""label\s*:\s*['"]raw_secret['"]""",
    ]

    for pattern in forbidden_visible_patterns:
        assert re.search(pattern, source) is None, pattern


def test_13e_h2_revoke_flow_references_are_preserved() -> None:
    source = read(ADMIN_API_KEYS_JS)

    assert "revoke" in source.lower()
    assert "window.confirm" in source or "confirm(" in source


def test_13e_h2_admin_api_keys_cache_is_bumped() -> None:
    html = read(ADMIN_HTML)

    assert "admin_api_keys.js?v=adminapikeys13eh2" in html
