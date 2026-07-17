from pathlib import Path


def test_intake_preview_route_is_authenticated_and_non_persistent() -> None:
    source = Path("processual_api/main.py").read_text(encoding="utf-8")

    assert '@app.post("/settings/admin/operator-pilot-handoff/intake-preview")' in source
    assert 'require_scope("admin:integration_readiness:review")' in source
    assert "build_operator_pilot_handoff_intake_preview(payload)" in source
    assert "status_code=422" in source


def test_intake_preview_route_has_no_runtime_or_storage_call() -> None:
    source = Path("processual_api/main.py").read_text(encoding="utf-8")
    start = source.index("def admin_operator_pilot_handoff_intake_preview_17c_r1")
    end = source.index("# END PILOT_HANDOFF_17C_R1_INTAKE_PREVIEW_ROUTE", start)
    route = source[start:end]

    for forbidden in (
        "write_text(",
        "open(",
        "requests.",
        "httpx.",
        "activate",
        "issue_activation_permission_key",
    ):
        assert forbidden not in route
