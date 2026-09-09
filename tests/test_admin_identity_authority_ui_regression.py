from pathlib import Path


ADMIN_AUTH_BRIDGE = Path("processual_api/static/js/admin_auth_bridge.js")
ADMIN_SESSION = Path("processual_api/static/js/admin_session.js")


def test_admin_auth_bridge_uses_only_canonical_identity_session_token() -> None:
    source = ADMIN_AUTH_BRIDGE.read_text(encoding="utf-8")

    assert "const IDENTITY_TOKEN_KEY = 'maestro_token'" in source
    assert "sessionStorage.getItem(key)" in source
    assert "localStorage.getItem" not in source
    assert "scanStorage" not in source
    assert "preferredKeys" not in source
    assert "legacyStorageScanEnabled: false" in source
    assert "localStorageUsedForAuth: false" in source


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
