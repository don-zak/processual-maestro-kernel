from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_HTML = ROOT / "processual_api" / "static" / "admin.html"
ADMIN_API_KEYS_JS = ROOT / "processual_api" / "static" / "js" / "admin_api_keys.js"
ADMIN_HARDENING_CSS = (
    ROOT / "processual_api" / "static" / "css" / "admin_ui_hardening_13c.css"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_function(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.find(marker)
    assert start >= 0, f"{name} function should exist"

    params_start = source.find("(", start)
    assert params_start >= 0, f"{name} function should have parameters"

    paren_depth = 0
    params_end = -1
    for index in range(params_start, len(source)):
        char = source[index]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
            if paren_depth == 0:
                params_end = index
                break

    assert params_end > params_start, f"{name} parameters should close"

    brace_start = source.find("{", params_end)
    assert brace_start >= 0, f"{name} function should have a body"

    brace_depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
            if brace_depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"{name} function body was not closed")


def test_13e_final_api_keys_cache_bumps_are_preserved() -> None:
    html = _read(ADMIN_HTML)

    assert "admin_api_keys.js?v=adminapikeys13eh2" in html
    assert "admin_ui_hardening_13c.css?v=adminui13c-13eh3r2toggle" in html


def test_13e_final_metadata_card_helpers_and_classes_are_preserved() -> None:
    js = _read(ADMIN_API_KEYS_JS)

    expected_markers = [
        "function renderSupervisorSessionKeyRows",
        "function renderRows",
        "function metadataDisplayValue",
        "function renderMetadataCardFields",
        "function renderMetadataDetailsCard",
        "admin-api-key-metadata-card",
        "admin-supervisor-session-metadata-card",
        "admin-api-key-metadata-card-list",
        "admin-supervisor-session-metadata-card-list",
        "admin-api-key-metadata-card-summary",
        "admin-api-key-metadata-card-toggle",
        "admin-api-key-metadata-card-toggle-open",
        "admin-api-key-metadata-card-toggle-close",
        "admin-api-key-metadata-card-body",
        ">Open<",
        ">Close<",
    ]

    for marker in expected_markers:
        assert marker in js


def test_13e_final_native_collapsible_and_revoke_controls_are_preserved() -> None:
    js = _read(ADMIN_API_KEYS_JS)

    expected_markers = [
        "<details",
        "<summary",
        "admin-api-key-revoke",
        "admin-supervisor-key-revoke",
        "data-key-id",
        "renderMetadataDetailsCard",
    ]

    for marker in expected_markers:
        assert marker in js


def test_13e_final_metadata_tables_are_not_restored_in_api_key_renderer() -> None:
    js = _read(ADMIN_API_KEYS_JS)
    render_rows = _extract_function(js, "renderRows")

    forbidden_markers = [
        "admin-api-key-metadata-table",
        "api-key-metadata-table",
        "<table",
    ]

    for marker in forbidden_markers:
        assert marker not in render_rows


def test_13e_final_metadata_card_css_contract_is_preserved() -> None:
    css = _read(ADMIN_HARDENING_CSS)

    expected_markers = [
        "#page-admin-api-keys .admin-api-key-metadata-card-list",
        "#page-admin-api-keys .admin-api-key-metadata-card",
        "#page-admin-api-keys .admin-api-key-metadata-card-summary",
        "#page-admin-api-keys .admin-api-key-metadata-card-toggle",
        "#page-admin-api-keys .admin-api-key-metadata-card-body",
        ".admin-api-key-metadata-card:not([open]) .admin-api-key-metadata-card-body",
        ".admin-api-key-metadata-card[open] .admin-api-key-metadata-card-body",
        "display: none",
        "display: block",
    ]

    for marker in expected_markers:
        assert marker in css
