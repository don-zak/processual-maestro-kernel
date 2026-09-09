from pathlib import Path


ADMIN_JS_DIR = Path("processual_api/static/js")
ADMIN_HTML = Path("processual_api/static/admin.html")
QUARANTINED_LEGACY_CONSUMERS = {"admin_client_requests.js"}
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


def test_no_new_admin_module_may_read_legacy_auth_token_storage() -> None:
    offenders: list[str] = []
    for path in sorted(ADMIN_JS_DIR.glob("admin_*.js")):
        source = path.read_text(encoding="utf-8")
        matches = [needle for needle in FORBIDDEN_AUTH_READS if needle in source]
        if matches and path.name not in QUARANTINED_LEGACY_CONSUMERS:
            offenders.append(f"{path}: {', '.join(matches)}")

    assert not offenders, "Legacy admin auth storage reads found:\n" + "\n".join(offenders)


def test_quarantined_legacy_consumer_is_loaded_after_canonical_bridge() -> None:
    html = ADMIN_HTML.read_text(encoding="utf-8")
    bridge_position = html.index("admin_auth_bridge.js")
    legacy_position = html.index("admin_client_requests.js")

    assert bridge_position < legacy_position


def test_admin_auth_bridge_purges_legacy_credentials_before_consumers_load() -> None:
    bridge = (ADMIN_JS_DIR / "admin_auth_bridge.js").read_text(encoding="utf-8")

    assert "const IDENTITY_TOKEN_KEY = 'maestro_token'" in bridge
    assert "return sessionValue(IDENTITY_TOKEN_KEY)" in bridge
    assert "purgeLegacyCredentialStorage();" in bridge
    assert "removeStorageKey(localStorage, IDENTITY_TOKEN_KEY)" in bridge
    assert "removeStorageKey(localStorage, SUPERVISOR_SESSION_KEY)" in bridge
    assert "'access_token'" in bridge
    assert "'auth_token'" in bridge
    assert "'admin_token'" in bridge
    assert "'pmk_admin_supervisor_session'" in bridge
    assert "localStorage.getItem" not in bridge


def test_only_known_quarantined_consumer_contains_legacy_bearer_reads() -> None:
    offenders: set[str] = set()
    for path in sorted(ADMIN_JS_DIR.glob("admin_*.js")):
        source = path.read_text(encoding="utf-8")
        if any(needle in source for needle in FORBIDDEN_AUTH_READS):
            offenders.add(path.name)

    assert offenders <= QUARANTINED_LEGACY_CONSUMERS
