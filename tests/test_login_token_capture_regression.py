
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def test_login_loads_token_capture_early():
    html = (STATIC_DIR / "login.html").read_text(encoding="utf-8")

    assert "/console/js/login_token_capture.js" in html
    assert html.index("login_token_capture.js") < html.index("</head>")


def test_login_token_capture_persists_admin_tokens():
    script = (STATIC_DIR / "js" / "login_token_capture.js").read_text(encoding="utf-8")

    required = [
        "persistAuthPayload",
        "access_token",
        "admin_access_token",
        "admin_session",
        "processual_session",
        "loginTokenCapturingFetch",
        "PMK_LOGIN_TOKEN_CAPTURE",
    ]

    for token in required:
        assert token in script
