from pathlib import Path

STATIC_ROOT = Path("processual_api/static")
STATIC_EXTENSIONS = {".html", ".js", ".css"}
MOJIBAKE_TOKENS = (
    "\u00c3",
    "\u00c2",
    "\u00e2",
    "\u00f0",
    "\ufffd",
)
NON_UTF8_BOMS = (
    b"\xff\xfe",
    b"\xfe\xff",
)
UTF8_BOM = b"\xef\xbb\xbf"


def _static_text_files() -> list[Path]:
    return sorted(
        path
        for path in STATIC_ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in STATIC_EXTENSIONS
    )


def test_static_ui_files_are_strict_utf8_without_mojibake_tokens() -> None:
    offenders: list[str] = []
    for path in _static_text_files():
        data = path.read_bytes()
        if data.startswith(NON_UTF8_BOMS):
            offenders.append(f"{path}:non-utf8-bom")
            continue
        if data.startswith(UTF8_BOM):
            offenders.append(f"{path}:utf8-bom")

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            offenders.append(f"{path}:utf8-decode-error:{exc}")
            continue

        for token in MOJIBAKE_TOKENS:
            if token in text:
                offenders.append(f"{path}:{token!r}")

    assert offenders == []


def test_console_html_declares_utf8_and_preserves_repaired_symbols() -> None:
    html = Path("processual_api/static/index.html").read_text(encoding="utf-8")

    assert "<meta charset=\"utf-8\"/>" in html
    assert "Processual Maestro \u2014 Console" in html
    assert "v2.0.0 \u2014 production" in html
    assert "<span class=\"nav-ico\">\u2699</span><span>Settings</span>" in html
    assert "\u00e2" not in html
