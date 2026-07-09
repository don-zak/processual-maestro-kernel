import re
from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html").read_text(encoding="utf-8")
ADMIN_API_KEYS_JS = Path("processual_api/static/js/admin_api_keys.js").read_text(
    encoding="utf-8"
)
STATIC_SOURCES = "\n".join(
    path.read_text(encoding="utf-8")
    for path in Path("processual_api/static").rglob("*")
    if path.suffix in {".html", ".js"}
)


RENAMED_STATIC_IDS = {
    "admin-api-key-generate-btn": "admin-api-key-static-generate-btn",
    "admin-api-key-refresh-btn": "admin-api-key-static-refresh-btn",
    "admin-api-key-create-result": "admin-api-key-static-create-result",
}


def test_static_api_key_placeholder_ids_are_namespaced_13e():
    for old_id, new_id in RENAMED_STATIC_IDS.items():
        assert f'id="{old_id}"' not in ADMIN_HTML
        assert f'id="{new_id}"' in ADMIN_HTML


def test_dynamic_api_key_runtime_ids_remain_owned_by_javascript_13e():
    for old_id in RENAMED_STATIC_IDS:
        assert old_id in ADMIN_API_KEYS_JS


def test_admin_api_key_label_id_is_dynamic_only_13e():
    assert 'id="admin-api-key-label"' not in ADMIN_HTML
    assert 'id="admin-api-key-static-label"' not in ADMIN_HTML
    assert 'admin-api-key-label' in ADMIN_API_KEYS_JS


def test_profile_label_input_uses_unique_id_13e():
    duplicate_profile_label = re.search(
        r'<input\b(?=[^>]*id="admin-api-key-label")'
        r'(?=[^>]*placeholder="client-or-team-name")',
        STATIC_SOURCES,
    )
    renamed_profile_label = re.search(
        r'<input\b(?=[^>]*id="admin-api-key-profile-label")'
        r'(?=[^>]*placeholder="client-or-team-name")',
        STATIC_SOURCES,
    )

    assert duplicate_profile_label is None
    assert renamed_profile_label is not None

def test_profile_label_control_references_unique_id_13e():
    assert 'for="admin-api-key-profile-label"' in STATIC_SOURCES
    assert (
        "document.getElementById('admin-api-key-profile-label')"
        in STATIC_SOURCES
    )
