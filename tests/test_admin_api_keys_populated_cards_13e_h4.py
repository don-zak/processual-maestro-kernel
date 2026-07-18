from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


def test_h4_populated_api_key_rows_render_metadata_cards_without_restoring_tables() -> None:
    source = _read(ADMIN_API_KEYS_JS)
    render_rows = _extract_function(source, "renderRows")

    assert "renderMetadataDetailsCard" in render_rows
    assert "admin-api-key-metadata-card" in source
    assert "admin-api-key-metadata-card-list" in source
    assert "admin-api-key-revoke" in render_rows

    forbidden_table_markers = [
        "admin-api-key-metadata-table",
        "api-key-metadata-table",
        "<table",
    ]
    for marker in forbidden_table_markers:
        assert marker not in render_rows


def test_h4_metadata_details_card_keeps_native_collapsible_open_close_toggle() -> None:
    source = _read(ADMIN_API_KEYS_JS)
    details_card = _extract_function(source, "renderMetadataDetailsCard")

    assert "<details" in details_card
    assert "<summary" in details_card
    assert "admin-api-key-metadata-card-summary" in details_card
    assert "admin-api-key-metadata-card-toggle" in details_card
    assert "admin-api-key-metadata-card-toggle-open" in details_card
    assert "admin-api-key-metadata-card-toggle-close" in details_card
    assert ">Open<" in details_card
    assert ">Close<" in details_card
    assert "admin-api-key-metadata-card-body" in details_card


def test_h4_populated_api_key_card_path_preserves_expected_safe_fields_and_actions() -> None:
    source = _read(ADMIN_API_KEYS_JS)
    render_rows = _extract_function(source, "renderRows")

    expected_populated_path_markers = [
        "category",
        "client_id",
        "user_id",
        "plan_id",
        "purpose",
        "label",
        "issued_to",
        "status",
        "created_at",
        "revoked_at",
    ]

    for marker in expected_populated_path_markers:
        assert marker in source

    assert "admin-api-key-revoke" in render_rows
    assert "data-key-id" in render_rows
    assert "raw_secret_visible" not in render_rows
    assert "raw_secret" not in render_rows
    assert "raw_key" not in render_rows


def test_h4_metadata_card_css_keeps_body_closed_until_native_details_open() -> None:
    css = _read(ADMIN_HARDENING_CSS)

    assert "#page-admin-api-keys .admin-api-key-metadata-card-body" in css
    assert (
        "#page-admin-api-keys .admin-api-key-metadata-card:not([open]) "
        ".admin-api-key-metadata-card-body"
    ) in css
    assert (
        "#page-admin-api-keys .admin-api-key-metadata-card[open] "
        ".admin-api-key-metadata-card-body"
    ) in css
    assert "display: none" in css
    assert "display: block" in css
