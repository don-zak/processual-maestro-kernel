from pathlib import Path


ADMIN_AUTH_BRIDGE = Path("processual_api/static/js/admin_auth_bridge.js")
ADMIN_SESSION = Path("processual_api/static/js/admin_session.js")
ADMIN_API_KEYS = Path("processual_api/static/js/admin_api_keys.js")


def test_admin_auth_bridge_uses_only_canonical_identity_session_token() -> None:
    source = ADMIN_AUTH_BRIDGE.read_text(encoding="utf-8")

    assert "const IDENTITY_TOKEN_KEY = 'maestro_token'" in source
    assert "sessionStorage.getItem(key)" in source
    assert "localStorage.getItem" not in source
    assert "scanStorage" not in source
    assert "preferredKeys" not in source
    assert "legacyStorageScanEnabled: false" in source
    assert "localStorageUsedForAuth: false" in source


def test_admin_api_keys_has_no_legacy_auth_token_fallback() -> None:
    source = ADMIN_API_KEYS.read_text(encoding="utf-8")

    assert "window.PMK_ADMIN_AUTH" in source
    assert "localStorage.getItem('access_token')" not in source
    assert "localStorage.getItem('auth_token')" not in source
    assert "localStorage.getItem('admin_token')" not in source
    assert "sessionStorage.getItem('access_token')" not in source
    assert "sessionStorage.getItem('auth_token')" not in source
    assert "sessionStorage.getItem('admin_token')" not in source


def test_admin_evaluation_authority_is_backend_platform_admin_authority() -> None:
    source = ADMIN_SESSION.read_text(encoding="utf-8")

    assert "const AUTHORITY_ENDPOINT = '/settings/admin/evaluation-grants/authority'" in source
    assert "authority?.authorized !== true" in source
    assert "authority?.authority !== 'platform_admin'" in source
    assert "isAdminSession" not in source
    assert "canManageEvaluationGrants" not in source
    assert "ADMIN_ROLES" not in source
    assert "EVALUATION_ADMIN_ROLES" not in source


def test_expired_admin_identity_session_fails_closed() -> None:
    source = ADMIN_SESSION.read_text(encoding="utf-8")

    assert "response.status === 401 || response.status === 403" in source
    assert "clearIdentitySession" in source
    assert "Protected controls are locked" in source
    assert "auth-expired" in source


def test_verified_platform_admin_enters_external_evaluation_by_default() -> None:
    source = ADMIN_SESSION.read_text(encoding="utf-8")

    assert "function activateExternalEvaluationEntry()" in source
    assert "option[value=\"${EXTERNAL_CATEGORY}\"]" in source
    assert "select.value = EXTERNAL_CATEGORY" in source
    assert "select.dispatchEvent(new Event('change', { bubbles: true }))" in source
    assert "loadProtectedEvaluationControls();" in source
    assert "window.setTimeout(activateExternalEvaluationEntry, 0);" in source
    assert "document.body.dataset.adminExternalEvaluationEntry = 'active'" in source
    assert ".click()" not in source


def test_external_evaluation_hides_only_legacy_surfaces_and_preserves_lifecycle_container() -> None:
    source = ADMIN_SESSION.read_text(encoding="utf-8")

    assert "function setExternalEvaluationSurfaceVisibility(selected)" in source
    assert "admin-supervisor-session-key-panel" in source
    assert "admin-supervisor-audit-summary" in source
    assert "admin-api-key-lifecycle-summary" in source
    assert "admin-api-key-static-generate-btn" in source
    assert ".closest('.grid-2-eq')" in source
    assert "page?.firstElementChild" not in source
    assert "node.hidden = true" in source
    assert "node.style.display = 'none'" in source
    assert "node.hidden = node.dataset.externalEvaluationPreviousHidden === 'true'" in source
    assert "node.style.display = node.dataset.externalEvaluationPreviousDisplay || ''" in source
    assert "setExternalEvaluationSurfaceVisibility(selected);" in source
