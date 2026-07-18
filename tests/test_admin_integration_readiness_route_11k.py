from pathlib import Path

from processual_api.routers.settings import _admin_integration_readiness_payload


def test_admin_integration_readiness_payload_is_safe() -> None:
    payload = _admin_integration_readiness_payload()
    assert payload["status"] == "ready"
    assert payload["surface"] == "admin_integration_readiness"
    assert payload["summary"]["total"] == len(payload["checks"])
    assert payload["summary"]["production_allowed"] == 0
    assert payload["summary"]["runtime_connector_approved"] == 0
    assert payload["guardrails"]["read_only"] is True
    assert payload["guardrails"]["raw_secret_visible"] is False
    assert payload["guardrails"]["production_allowed"] is False
    assert payload["guardrails"]["runtime_connector_approved"] is False
    assert payload["guardrails"]["external_http_enabled"] is False

    for check in payload["checks"]:
        assert check["readiness_check_id"]
        assert check["adapter_contract_id"]
        assert check["credential_profile_id"]
        assert isinstance(check["missing_inputs"], list)
        assert isinstance(check["missing_security_controls"], list)
        assert check["production_allowed"] is False
        assert check["runtime_connector_approved"] is False


def test_admin_integration_readiness_route_is_admin_scoped() -> None:
    source = Path("processual_api/routers/settings.py").read_text(encoding="utf-8")
    assert '"/admin/integration-readiness"' in source
    assert "get_admin_integration_readiness" in source
    assert "Depends(get_current_user)" in source
    assert "_require_admin_client_requests_read(current_user)" in source
    assert "list_integration_readiness_checks" in source
    assert "summarize_integration_readiness" in source
    assert '"raw_secret_visible": False' in source
    assert '"production_allowed": False' in source
    assert '"runtime_connector_approved": False' in source
