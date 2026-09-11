from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_admin_runtime_uses_auth_bridge_for_backend_headers():
    runtime = (STATIC_DIR / "js" / "admin_runtime.js").read_text(encoding="utf-8")
    bridge = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    runtime_required = [
        "PMK_ADMIN_AUTH.headers",
        "credentials: 'include'",
        "fetch(path",
        "Admin Auth Transport",
        "Bearer token found",
    ]

    for token in runtime_required:
        assert token in runtime

    bridge_required = [
        "function headers(",
        "Authorization",
        "X-API-Key",
        "diagnostic",
        "installFetchBridge",
        "PMK_ADMIN_AUTH",
    ]

    for token in bridge_required:
        assert token in bridge


def test_admin_fetch_bridge_coalesces_only_equivalent_read_requests():
    bridge = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    required = [
        "const READ_COALESCE_TTL_MS = 750;",
        "const READ_COALESCE_MAX_ENTRIES = 128;",
        "const inFlightReads = new Map();",
        "const recentReads = new Map();",
        "function shouldCoalesceRead(url, method, init)",
        "if (method !== 'GET') return false;",
        "if (init?.body !== undefined && init?.body !== null) return false;",
        "if (init?.signal) return false;",
        "requestHeaders.get('Accept') || ''",
        "requestHeaders.get('Authorization') || ''",
        "requestHeaders.get('X-API-Key') || ''",
        "requestHeaders.get('X-Supervisor-Session-Key') || ''",
        "existing.then(cloneResponse)",
        "return networkRequest.then(cloneResponse);",
    ]

    for token in required:
        assert token in bridge


def test_admin_fetch_bridge_does_not_add_entity_headers_to_empty_reads():
    bridge = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    assert "(method === 'GET' || method === 'HEAD')" in bridge
    assert "nextInit.body === undefined" in bridge
    assert "!explicitHeaders.has('Content-Type')" in bridge
    assert "nextInit.headers.delete('Content-Type');" in bridge
    assert "if (!shouldCoalesceRead(url, method, nextInit))" in bridge


def test_admin_fetch_bridge_preserves_no_store_and_mutation_semantics():
    bridge = (STATIC_DIR / "js" / "admin_auth_bridge.js").read_text(encoding="utf-8")

    assert "const cacheMode = String(nextInit.cache || '').toLowerCase();" in bridge
    assert "if (cacheMode !== 'no-store')" in bridge
    assert "if (method !== 'GET') return false;" in bridge
    assert "return originalFetch(input, nextInit);" in bridge


def test_admin_cards_are_scrollable_for_long_backend_output():
    cleanup = (STATIC_DIR / "js" / "admin_layout_cleanup.js").read_text(encoding="utf-8")

    required = [
        "max-height:440px",
        "overflow:auto",
        "#admin-api-key-create-result,#admin-api-key-list",
    ]

    for token in required:
        assert token in cleanup
