from pathlib import Path

ADMIN_HTML = Path("processual_api/static/admin.html").read_text(encoding="utf-8")
ADMIN_API_KEYS_JS = Path("processual_api/static/js/admin_api_keys.js").read_text(
    encoding="utf-8"
)


def test_supervisor_metadata_note_does_not_render_raw_field_names_13e_d2():
    assert "Safe metadata omits raw_key" not in ADMIN_API_KEYS_JS
    assert "key_hash." not in ADMIN_API_KEYS_JS
    assert "raw_secret" not in ADMIN_API_KEYS_JS

    assert "Safe metadata omits secret values" in ADMIN_API_KEYS_JS
    assert "stored hashes" in ADMIN_API_KEYS_JS


def test_admin_api_keys_cache_marker_bumped_for_13e_d2():
    assert (
        "admin_api_keys.js?v=adminapikeys13ed2" in ADMIN_HTML
        or "admin_api_keys.js?v=adminapikeys13eh2" in ADMIN_HTML
    )
    assert "admin_api_keys.js?v=adminapikeys13df2" not in ADMIN_HTML
