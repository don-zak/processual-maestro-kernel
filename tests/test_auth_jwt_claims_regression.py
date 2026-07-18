from pathlib import Path

from processual_api.auth import security

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class FakeJWT:
    captured_payload = None

    @classmethod
    def encode(cls, payload, _secret, algorithm):
        cls.captured_payload = payload
        return "fake.jwt.token"


def test_create_access_token_includes_ui_session_claims(monkeypatch):
    FakeJWT.captured_payload = None
    monkeypatch.setattr(security, "jwt", FakeJWT)

    token = security.create_access_token(
        subject="admin",
        role="admin",
        client_id="admin",
        session_type="ui_admin",
        scopes=["*", "admin:settings"],
    )

    payload = FakeJWT.captured_payload

    assert token == "fake.jwt.token"
    assert payload is not None
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert payload["client_id"] == "admin"
    assert payload["session_type"] == "ui_admin"
    assert payload["scopes"] == ["*", "admin:settings"]
    assert "exp" in payload
    assert "iat" in payload


def test_login_route_issues_admin_ui_jwt_claims():
    source = read_text(ROOT / "processual_api" / "auth" / "router.py")

    required_markers = [
        "create_access_token(",
        'role="admin"',
        'client_id="admin"',
        'session_type="ui_admin"',
        'scopes=["*"]',
    ]

    missing = [
        marker for marker in required_markers
        if marker not in source
    ]

    assert not missing, f"Missing auth token route JWT claim markers: {missing}"
