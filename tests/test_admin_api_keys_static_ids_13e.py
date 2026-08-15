from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html").read_text(encoding="utf-8")
ADMIN_API_KEYS_JS = Path("processual_api/static/js/admin_api_keys.js").read_text(
    encoding="utf-8"
)
RUNTIME_FIXUPS_JS = Path(
    "processual_api/static/js/admin_runtime_fixups.js"
).read_text(encoding="utf-8")


RENAMED_STATIC_IDS = {
    "admin-api-key-generate-btn": "admin-api-key-static-generate-btn",
    "admin-api-key-refresh-btn": "admin-api-key-static-refresh-btn",
    "admin-api-key-create-result": "admin-api-key-static-create-result",
}


def test_static_api_key_placeholder_ids_are_namespaced_13e():
    for old_id, new_id in RENAMED_STATIC_IDS.items():
        assert f'id="{old_id}"' not in ADMIN_HTML
        assert f'id="{new_id}"' in ADMIN_HTML


def test_dynamic_api_key_runtime_ids_remain_owned_by_primary_renderer_13e():
    for old_id in RENAMED_STATIC_IDS:
        assert old_id in ADMIN_API_KEYS_JS


def test_admin_api_key_label_id_is_dynamic_only_13e():
    assert 'id="admin-api-key-label"' not in ADMIN_HTML
    assert 'id="admin-api-key-static-label"' not in ADMIN_HTML
    assert 'admin-api-key-label' in ADMIN_API_KEYS_JS


def test_deprecated_runtime_profile_controls_are_not_reintroduced_13e():
    assert "admin-api-key-profile-controls" not in RUNTIME_FIXUPS_JS
    assert "admin-api-key-profile-label" not in RUNTIME_FIXUPS_JS
    assert "generateProfiledApiKey" not in RUNTIME_FIXUPS_JS
    assert "request('POST', '/settings/api-keys'" not in RUNTIME_FIXUPS_JS
