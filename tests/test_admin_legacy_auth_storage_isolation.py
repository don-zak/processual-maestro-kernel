from pathlib import Path


ADMIN_JS_DIR = Path("processual_api/static/js")
FORBIDDEN_AUTH_READS = (
    "localStorage.getItem('access_token')",
    'localStorage.getItem("access_token")',
    "localStorage.getItem('auth_token')",
    'localStorage.getItem("auth_token")',
    "localStorage.getItem('admin_token')",
    'localStorage.getItem("admin_token")',
    "sessionStorage.getItem('access_token')",
    'sessionStorage.getItem("access_token")',
    "sessionStorage.getItem('auth_token')",
    'sessionStorage.getItem("auth_token")',
    "sessionStorage.getItem('admin_token')",
    'sessionStorage.getItem("admin_token")',
)


def test_admin_modules_do_not_read_legacy_auth_token_storage() -> None:
    offenders: list[str] = []
    for path in sorted(ADMIN_JS_DIR.glob("admin_*.js")):
        source = path.read_text(encoding="utf-8")
        matches = [needle for needle in FORBIDDEN_AUTH_READS if needle in source]
        if matches:
            offenders.append(f"{path}: {', '.join(matches)}")

    assert not offenders, "Legacy admin auth storage reads found:\n" + "\n".join(offenders)


def test_admin_auth_bridge_is_the_canonical_bearer_source() -> None:
    bridge = (ADMIN_JS_DIR / "admin_auth_bridge.js").read_text(encoding="utf-8")

    assert "const IDENTITY_TOKEN_KEY = 'maestro_token'" in bridge
    assert "return sessionValue(IDENTITY_TOKEN_KEY)" in bridge
    assert "localStorage.getItem" not in bridge
