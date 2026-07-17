from pathlib import Path

import jwt
import pytest
from fastapi import HTTPException

from processual_api.auth.security import create_access_token, verify_access_token
from processual_api.settings import settings


def test_security_dependencies_use_pyjwt_without_python_ecdsa_backend():
    project = Path("pyproject.toml").read_text(encoding="utf-8")

    assert project.count('"PyJWT[crypto]>=2.13"') == 2
    assert "python-jose" not in project


def test_auth_and_subscription_runtime_no_longer_import_python_jose():
    auth_source = Path("processual_api/auth/security.py").read_text(encoding="utf-8")
    subscription_source = Path("processual_api/middleware/subscription.py").read_text(encoding="utf-8")

    assert "from jose" not in auth_source
    assert "from jose" not in subscription_source
    assert "import jwt" in auth_source
    assert "import jwt" in subscription_source


def test_pyjwt_access_token_round_trip_preserves_governed_claims():
    token = create_access_token(
        "jwt-migration-user",
        role="admin",
        client_id="jwt-migration-client",
        session_type="jwt",
        scopes=["admin:integration:read"],
    )

    payload = verify_access_token(token)

    assert payload["sub"] == "jwt-migration-user"
    assert payload["role"] == "admin"
    assert payload["client_id"] == "jwt-migration-client"
    assert payload["session_type"] == "jwt"
    assert payload["scopes"] == ["admin:integration:read"]
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)


def test_pyjwt_invalid_token_preserves_unauthorized_contract():
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token("not-a-valid-jwt")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"


def test_pyjwt_rejects_token_signed_with_unapproved_algorithm():
    token = jwt.encode(
        {"sub": "algorithm-downgrade-probe"},
        settings.jwt_secret,
        algorithm="HS512",
    )

    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid or expired token"
