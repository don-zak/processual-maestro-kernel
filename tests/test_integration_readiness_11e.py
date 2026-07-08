from pathlib import Path

import pytest

from processual_api.integrations.credential_profiles import list_credential_profiles
from processual_api.integrations.integration_readiness import (
    evaluate_integration_readiness,
    get_integration_readiness_check,
    list_integration_readiness_checks,
    summarize_integration_readiness,
    validate_integration_readiness_checks,
)


def _adapter_contract_ids() -> set[str]:
    from processual_api.integrations import adapter_contracts

    if hasattr(adapter_contracts, "list_adapter_contracts"):
        return {
            contract.contract_id
            for contract in adapter_contracts.list_adapter_contracts()
        }

    registry = getattr(adapter_contracts, "ADAPTER_CONTRACTS", ())
    if isinstance(registry, dict):
        return {contract.contract_id for contract in registry.values()}

    return {contract.contract_id for contract in registry}


def test_readiness_checks_are_declared_for_credential_profiles() -> None:
    checks = list_integration_readiness_checks()
    profile_ids = {
        profile.credential_profile_id for profile in list_credential_profiles()
    }
    check_profile_ids = {check.credential_profile_id for check in checks}

    assert checks
    assert profile_ids.issubset(check_profile_ids)


def test_readiness_checks_reference_existing_adapter_contracts() -> None:
    adapter_contract_ids = _adapter_contract_ids()

    for check in list_integration_readiness_checks():
        assert check.contract_id in adapter_contract_ids


def test_default_readiness_is_blocked_pending_customer_inputs() -> None:
    checks = list_integration_readiness_checks()

    assert checks
    assert all(check.sandbox_ready is False for check in checks)
    assert all(check.production_allowed is False for check in checks)
    assert all(check.runtime_connector_approved is False for check in checks)
    assert all(check.missing_inputs for check in checks)
    assert all(check.blocking_reasons for check in checks)


def test_complete_inputs_make_checks_ready_for_sandbox_only() -> None:
    required_inputs = {
        item
        for profile in list_credential_profiles()
        for item in profile.required_customer_inputs
    }
    required_controls = {
        item
        for profile in list_credential_profiles()
        for item in profile.required_security_controls
    }

    checks = evaluate_integration_readiness(
        provided_inputs=required_inputs,
        approved_security_controls=required_controls,
    )

    assert checks
    assert all(check.status == "ready_for_sandbox_review" for check in checks)
    assert all(check.sandbox_ready is True for check in checks)
    assert all(check.production_allowed is False for check in checks)
    assert all(check.runtime_connector_approved is False for check in checks)


def test_security_controls_can_block_after_customer_inputs_are_present() -> None:
    required_inputs = {
        item
        for profile in list_credential_profiles()
        for item in profile.required_customer_inputs
    }

    checks = evaluate_integration_readiness(provided_inputs=required_inputs)

    assert checks
    assert all(
        check.status == "blocked_missing_security_controls" for check in checks
    )
    assert all("missing_security_controls" in check.blocking_reasons for check in checks)


def test_get_readiness_check_by_id() -> None:
    first = list_integration_readiness_checks()[0]

    assert get_integration_readiness_check(first.readiness_check_id) == first

    with pytest.raises(KeyError):
        get_integration_readiness_check("missing:readiness")


def test_readiness_summary_is_safe_for_surfaces() -> None:
    summary = summarize_integration_readiness()

    assert summary["total"] > 0
    assert summary["blocked"] == summary["total"]
    assert summary["sandbox_ready"] == 0
    assert summary["production_allowed"] == 0
    assert summary["runtime_connector_approved"] == 0


def test_readiness_validation_has_no_issues() -> None:
    assert validate_integration_readiness_checks() == ()


def test_readiness_module_does_not_add_runtime_network_clients() -> None:
    source = Path(
        "processual_api/integrations/integration_readiness.py"
    ).read_text(encoding="utf-8")

    forbidden_runtime_markers = (
        "requests.",
        "httpx.",
        "aiohttp",
        "urllib.request",
        "socket.",
        "subprocess",
        "os.environ",
        "http://",
        "https://",
    )

    for marker in forbidden_runtime_markers:
        assert marker not in source


def test_document_records_11e_guardrails() -> None:
    document = Path(
        "docs/integrations/INTEGRATION_READINESS_11E.md"
    ).read_text(encoding="utf-8")

    assert "production_allowed = false" in document
    assert "runtime_connector_approved = false" in document
    assert "external HTTP" in document
    assert "real credentials" in document
    assert "customer-specific connector runtime" in document
