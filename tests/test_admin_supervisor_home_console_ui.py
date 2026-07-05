from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_admin_home_has_supervisor_operations_center() -> None:
    source = read_text("processual_api/static/admin.html")

    assert 'id="admin-supervisor-home-console"' in source
    assert "Supervisor Operations Center" in source
    assert "visibility hub for supervisor operations" in source
    assert 'href="#admin-supervisor-overview-counters"' in source
    assert 'href="#admin-supervisor-audit-summary"' in source
    assert 'href="#admin-api-key-lifecycle-summary"' in source


def test_supervisor_operations_center_appears_before_summary_cards() -> None:
    source = read_text("processual_api/static/admin.html")

    console_index = source.index('id="admin-supervisor-home-console"')
    overview_index = source.index('id="admin-supervisor-overview-counters"')
    audit_index = source.index('id="admin-supervisor-audit-summary"')
    keys_index = source.index('id="admin-api-key-lifecycle-summary"')

    assert console_index < overview_index
    assert console_index < audit_index
    assert console_index < keys_index


def test_supervisor_operations_center_preserves_safe_boundaries() -> None:
    source = read_text("processual_api/static/admin.html")
    start = source.index('id="admin-supervisor-home-console"')
    end = source.index('id="admin-supervisor-overview-counters"')
    fragment = source[start:end]

    assert "Backend enforcement remains authoritative" in fragment
    assert "no raw keys or provider secrets" in fragment
    assert "raw_key" not in fragment
    assert "key_hash" not in fragment
    assert "provider_secret" not in fragment
    assert "encrypted_key" not in fragment
