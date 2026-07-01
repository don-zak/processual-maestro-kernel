from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGIN_HTML = ROOT / "processual_api" / "static" / "login.html"


def test_login_page_sets_entry_mode_once_on_initial_admin_role():
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "let currentRole = 'admin';" in source
    assert source.count("setEntryMode(currentRole);") == 3


def test_login_page_updates_entry_mode_when_admin_tab_is_selected():
    source = LOGIN_HTML.read_text(encoding="utf-8")

    admin_block_start = source.index(
        "document.getElementById('tab-admin').addEventListener"
    )
    user_block_start = source.index(
        "document.getElementById('tab-user').addEventListener"
    )
    admin_block = source[admin_block_start:user_block_start]

    assert "currentRole = 'admin';" in admin_block
    assert "setEntryMode(currentRole);" in admin_block


def test_login_page_posts_selected_role_to_auth_token():
    source = LOGIN_HTML.read_text(encoding="utf-8")

    assert "role: currentRole" in source
