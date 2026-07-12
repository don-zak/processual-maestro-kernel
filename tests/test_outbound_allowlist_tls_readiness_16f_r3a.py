from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace
from pathlib import Path
from types import MappingProxyType

import pytest

from processual_api.integrations.outbound_allowlist_tls_readiness import (
    OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS,
    SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS,
    OutboundAllowlistTlsReadinessAssessment,
    OutboundAllowlistTlsReadinessContract,
    OutboundAllowlistTlsReadinessStatus,
    OutboundAllowlistTlsReferenceSubmission,
    TlsMinimumVersion,
    assess_outbound_allowlist_tls_readiness,
    get_outbound_allowlist_tls_readiness_contract,
    list_outbound_allowlist_tls_readiness_contracts,
    normalize_outbound_allowlist_tls_readiness_id,
    validate_outbound_allowlist_tls_readiness_contracts,
    validate_outbound_allowlist_tls_readiness_registry,
)

READINESS_ID = "telecom_ticketing_outbound_allowlist_tls_readiness"
INTAKE_ID = "telecom_ticketing_operator_sandbox_reference_intake"
CONNECTOR_ID = "telecom_ticketing_reference"

REQUIRED_REFERENCE_NAMES = (
    "allowlist_reference",
    "host_reference",
    "dns_policy_reference",
    "port_policy_reference",
    "ca_policy_reference",
    "certificate_pinning_policy_reference",
    "proxy_policy_reference",
    "egress_authorization_reference",
    "security_review_reference",
    "operator_approval_reference",
    "kill_switch_reference",
)

REQUIRED_TRUE_FIELDS = (
    "sandbox_only",
    "reference_only",
    "read_only",
    "allowlist_required",
    "tls_required",
    "egress_authorization_required",
    "security_review_required",
    "operator_approval_required",
    "kill_switch_required",
)

UNSAFE_FIELDS = (
    "allowlist_applied",
    "dns_resolution_performed",
    "port_opened",
    "tls_context_created",
    "ca_bundle_loaded",
    "certificate_loaded",
    "certificate_pin_applied",
    "proxy_configured",
    "egress_authorized",
    "kill_switch_armed",
    "connection_attempted",
    "external_http_enabled",
    "socket_access_enabled",
    "persistence_allowed",
    "background_task_allowed",
    "route_exposure_allowed",
    "runtime_enabled",
    "production_allowed",
    "automatic_activation_allowed",
)

PERMANENT_BLOCKERS = (
    "allowlist_application_disabled",
    "dns_resolution_disabled",
    "port_opening_disabled",
    "tls_context_creation_disabled",
    "ca_bundle_loading_disabled",
    "certificate_loading_disabled",
    "certificate_pinning_disabled",
    "proxy_configuration_disabled",
    "egress_authorization_execution_disabled",
    "kill_switch_arming_disabled",
    "connection_attempts_disabled",
    "external_http_disabled",
    "socket_access_disabled",
    "persistence_disabled",
    "background_tasks_disabled",
    "route_exposure_disabled",
    "runtime_disabled",
    "production_disabled",
    "automatic_activation_disabled",
)

MODULE_PATH = Path(
    "processual_api/integrations/"
    "outbound_allowlist_tls_readiness.py"
)


def _submission(
    tls_minimum_version: TlsMinimumVersion = (
        TlsMinimumVersion.TLS_1_2
    ),
) -> OutboundAllowlistTlsReferenceSubmission:
    return OutboundAllowlistTlsReferenceSubmission(
        submission_id="operator_network_policy_submission_ref",
        readiness_id=READINESS_ID,
        tls_minimum_version=tls_minimum_version,
        allowlist_reference="operator_allowlist_policy_ref",
        host_reference="operator_sandbox_host_ref",
        dns_policy_reference="operator_dns_policy_ref",
        port_policy_reference="operator_port_policy_ref",
        ca_policy_reference="operator_ca_policy_ref",
        certificate_pinning_policy_reference=(
            "operator_certificate_pinning_policy_ref"
        ),
        proxy_policy_reference="operator_proxy_policy_ref",
        egress_authorization_reference=(
            "operator_egress_authorization_ref"
        ),
        security_review_reference="security_review_case_ref",
        operator_approval_reference="operator_approval_case_ref",
        kill_switch_reference="operator_kill_switch_policy_ref",
    )


def test_registry_is_immutable_and_valid() -> None:
    assert isinstance(
        OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS,
        MappingProxyType,
    )
    assert validate_outbound_allowlist_tls_readiness_registry() == ()
    assert SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS == (
        READINESS_ID,
    )

    with pytest.raises(TypeError):
        OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS[
            "forged"
        ] = get_outbound_allowlist_tls_readiness_contract(
            READINESS_ID
        )


def test_list_and_get_preserve_contract_identity() -> None:
    contracts = list_outbound_allowlist_tls_readiness_contracts()

    assert len(contracts) == 1
    assert contracts[0] is get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )


def test_contract_declares_pending_default_deny_readiness() -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    assert contract.readiness_id == READINESS_ID
    assert contract.intake_id == INTAKE_ID
    assert contract.connector_id == CONNECTOR_ID
    assert contract.environment == "sandbox"
    assert contract.access_mode == "read"
    assert contract.selected_tls_minimum_version is (
        TlsMinimumVersion.PENDING_SELECTION
    )
    assert contract.supported_tls_minimum_versions == (
        TlsMinimumVersion.TLS_1_2,
        TlsMinimumVersion.TLS_1_3,
    )
    assert contract.required_references == REQUIRED_REFERENCE_NAMES
    assert contract.status is (
        OutboundAllowlistTlsReadinessStatus
        .PENDING_NETWORK_POLICY_REFERENCES
    )

    for name in REQUIRED_TRUE_FIELDS:
        assert getattr(contract, name) is True

    for name in UNSAFE_FIELDS:
        assert getattr(contract, name) is False


@pytest.mark.parametrize(
    "contract_type",
    (
        OutboundAllowlistTlsReadinessContract,
        OutboundAllowlistTlsReferenceSubmission,
        OutboundAllowlistTlsReadinessAssessment,
    ),
)
def test_models_are_frozen_slotted_dataclasses(
    contract_type: type[object],
) -> None:
    assert is_dataclass(contract_type)
    assert "__slots__" in contract_type.__dict__


def test_contract_instance_is_frozen() -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    with pytest.raises((FrozenInstanceError, AttributeError)):
        contract.runtime_enabled = True


@pytest.mark.parametrize(
    "value",
    (
        "",
        " ",
        " leading",
        "trailing ",
        "https://sandbox.operator.invalid",
        "http://sandbox.operator.invalid",
        "bearer forged",
        "password=forged",
        "token=forged",
        "secret=forged",
        "client_secret=forged",
        "private_key=forged",
        "certificate=forged",
        "api_key=forged",
        "raw_value=forged",
        "raw_payload=forged",
        "authorization: forged",
        "proxy-authorization: forged",
    ),
)
def test_normalizer_rejects_raw_or_invalid_reference(
    value: str,
) -> None:
    with pytest.raises(ValueError):
        normalize_outbound_allowlist_tls_readiness_id(value)


def test_normalizer_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalize_outbound_allowlist_tls_readiness_id(123)  # type: ignore[arg-type]


@pytest.mark.parametrize("field_name", REQUIRED_TRUE_FIELDS)
def test_contract_rejects_disabled_required_flag(
    field_name: str,
) -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    with pytest.raises(
        ValueError,
        match=rf"{field_name} must remain true",
    ):
        replace(contract, **{field_name: False})


@pytest.mark.parametrize("field_name", UNSAFE_FIELDS)
def test_contract_rejects_enabled_unsafe_flag(
    field_name: str,
) -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    with pytest.raises(
        ValueError,
        match=rf"{field_name} must remain false",
    ):
        replace(contract, **{field_name: True})


def test_contract_rejects_selected_tls_as_declared_state() -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    with pytest.raises(
        ValueError,
        match="must remain pending",
    ):
        replace(
            contract,
            selected_tls_minimum_version=(
                TlsMinimumVersion.TLS_1_2
            ),
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    (
        ("environment", "production", "sandbox-only"),
        ("access_mode", "write", "read-only"),
        ("intake_id", "forged_intake_ref", "governed R1 intake"),
        (
            "connector_id",
            "forged_connector_ref",
            "telecom ticketing connector",
        ),
    ),
)
def test_contract_rejects_changed_governed_identity(
    field_name: str,
    value: str,
    message: str,
) -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    with pytest.raises(ValueError, match=message):
        replace(contract, **{field_name: value})


def test_contract_validation_detects_duplicate() -> None:
    contract = get_outbound_allowlist_tls_readiness_contract(
        READINESS_ID
    )

    issues = validate_outbound_allowlist_tls_readiness_contracts(
        (contract, contract)
    )

    assert issues == (
        f"{READINESS_ID}:duplicate_readiness_id",
    )


def test_contract_validation_rejects_empty_or_wrong_type() -> None:
    assert validate_outbound_allowlist_tls_readiness_contracts(
        ()
    ) == ("no_outbound_readiness_declared",)

    issues = validate_outbound_allowlist_tls_readiness_contracts(
        ("forged",)  # type: ignore[arg-type]
    )

    assert issues == (
        "contract_0:invalid_outbound_readiness_type",
        "no_outbound_readiness_declared",
    )


@pytest.mark.parametrize(
    "tls_minimum_version",
    (
        TlsMinimumVersion.TLS_1_2,
        TlsMinimumVersion.TLS_1_3,
    ),
)
def test_supported_tls_submission_is_received_for_review(
    tls_minimum_version: TlsMinimumVersion,
) -> None:
    submission = _submission(tls_minimum_version)
    assessment = assess_outbound_allowlist_tls_readiness(
        READINESS_ID,
        submission,
    )

    assert assessment.status is (
        OutboundAllowlistTlsReadinessStatus
        .REFERENCES_RECEIVED_FOR_REVIEW
    )
    assert assessment.contract_valid is True
    assert assessment.intake_reference_valid is True
    assert assessment.submission_present is True
    assert assessment.tls_minimum_version_selected is True
    assert assessment.selected_tls_minimum_version_reference == (
        tls_minimum_version.value
    )
    assert assessment.reference_count == len(
        REQUIRED_REFERENCE_NAMES
    )
    assert assessment.required_reference_count == len(
        REQUIRED_REFERENCE_NAMES
    )
    assert assessment.references_valid is True
    assert assessment.ready_for_network_policy_review is True

    for name in UNSAFE_FIELDS:
        assert getattr(assessment, name) is False

    for blocker in PERMANENT_BLOCKERS:
        assert blocker in assessment.blocker_codes


def test_submission_rejects_pending_tls_version() -> None:
    with pytest.raises(
        ValueError,
        match="supported non-pending TLS",
    ):
        _submission(TlsMinimumVersion.PENDING_SELECTION)


def test_submission_rejects_wrong_tls_type() -> None:
    with pytest.raises(
        TypeError,
        match="must be TlsMinimumVersion",
    ):
        _submission("tls_1_2")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    REQUIRED_REFERENCE_NAMES,
)
def test_submission_rejects_raw_reference(
    field_name: str,
) -> None:
    submission = _submission()

    with pytest.raises(
        ValueError,
        match="reference name, not raw material",
    ):
        replace(
            submission,
            **{field_name: "https://raw.operator.invalid"},
        )


def test_submission_rejects_wrong_readiness_id() -> None:
    submission = _submission()

    with pytest.raises(
        ValueError,
        match="declared readiness",
    ):
        replace(
            submission,
            readiness_id="forged_readiness_reference",
        )


def test_pending_assessment_is_default_deny() -> None:
    assessment = assess_outbound_allowlist_tls_readiness(
        READINESS_ID
    )

    assert assessment.status is (
        OutboundAllowlistTlsReadinessStatus
        .PENDING_NETWORK_POLICY_REFERENCES
    )
    assert assessment.contract_valid is True
    assert assessment.intake_reference_valid is True
    assert assessment.submission_present is False
    assert assessment.tls_minimum_version_selected is False
    assert assessment.reference_count == 0
    assert assessment.references_valid is False
    assert assessment.ready_for_network_policy_review is False
    assert (
        "tls_minimum_version_selection_pending"
        in assessment.blocker_codes
    )

    for name in REQUIRED_REFERENCE_NAMES:
        assert f"{name}_pending" in assessment.blocker_codes

    for name in UNSAFE_FIELDS:
        assert getattr(assessment, name) is False


def test_assessment_is_deterministic() -> None:
    submission = _submission()

    first = assess_outbound_allowlist_tls_readiness(
        READINESS_ID,
        submission,
    )
    second = assess_outbound_allowlist_tls_readiness(
        READINESS_ID,
        submission,
    )

    assert first == second
    assert hash(first) == hash(second)


def test_assessment_rejects_wrong_submission_type() -> None:
    with pytest.raises(
        TypeError,
        match="OutboundAllowlistTlsReferenceSubmission or None",
    ):
        assess_outbound_allowlist_tls_readiness(
            READINESS_ID,
            "forged",  # type: ignore[arg-type]
        )


def test_forged_mismatched_submission_is_blocked() -> None:
    forged = object.__new__(
        OutboundAllowlistTlsReferenceSubmission
    )
    object.__setattr__(
        forged,
        "readiness_id",
        "forged_readiness_reference",
    )

    assessment = assess_outbound_allowlist_tls_readiness(
        READINESS_ID,
        forged,
    )

    assert assessment.status is (
        OutboundAllowlistTlsReadinessStatus.BLOCKED
    )
    assert assessment.submission_present is True
    assert assessment.tls_minimum_version_selected is False
    assert assessment.references_valid is False
    assert assessment.ready_for_network_policy_review is False


def test_forged_unsafe_contract_is_reported() -> None:
    contract = replace(
        get_outbound_allowlist_tls_readiness_contract(
            READINESS_ID
        )
    )
    object.__setattr__(contract, "external_http_enabled", True)
    object.__setattr__(contract, "runtime_enabled", True)

    issues = validate_outbound_allowlist_tls_readiness_contracts(
        (contract,)
    )

    assert (
        f"{READINESS_ID}:external_http_enabled_must_remain_disabled"
        in issues
    )
    assert (
        f"{READINESS_ID}:runtime_enabled_must_remain_disabled"
        in issues
    )


def test_unknown_readiness_is_rejected() -> None:
    with pytest.raises(
        KeyError,
        match="unknown outbound allowlist/TLS readiness",
    ):
        get_outbound_allowlist_tls_readiness_contract(
            "unknown_readiness_reference"
        )


def test_submission_contains_only_reference_metadata() -> None:
    submission = _submission()
    names = {field.name for field in fields(submission)}

    assert names == {
        "submission_id",
        "readiness_id",
        "tls_minimum_version",
        *REQUIRED_REFERENCE_NAMES,
    }

    serialized = repr(submission).lower()

    for marker in (
        "http://",
        "https://",
        "password=",
        "token=",
        "secret=",
        "private_key=",
        "api_key=",
        "raw_payload=",
    ):
        assert marker not in serialized


def test_module_has_no_network_or_runtime_imports() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", maxsplit=1)[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", maxsplit=1)[0])

    assert imported_roots.isdisjoint(
        {
            "aiohttp",
            "boto3",
            "google",
            "http",
            "httpx",
            "hvac",
            "requests",
            "socket",
            "ssl",
            "urllib",
            "azure",
        }
    )

    lowered = source.lower()

    for marker in (
        "socket.socket(",
        "socket.create_connection(",
        "socket.getaddrinfo(",
        "ssl.sslcontext(",
        "ssl.create_default_context(",
        "requests.get(",
        "requests.post(",
        "httpx.get(",
        "httpx.post(",
        "urllib.request.urlopen(",
        "os.environ",
        "getenv(",
        "subprocess.",
    ):
        assert marker not in lowered


def test_public_export_list_covers_direct_r3a_surface() -> None:
    import processual_api.integrations.outbound_allowlist_tls_readiness as module

    expected = {
        "OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS",
        "SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS",
        "OutboundAllowlistTlsReadinessAssessment",
        "OutboundAllowlistTlsReadinessContract",
        "OutboundAllowlistTlsReadinessStatus",
        "OutboundAllowlistTlsReferenceSubmission",
        "TlsMinimumVersion",
        "assess_outbound_allowlist_tls_readiness",
        "get_outbound_allowlist_tls_readiness_contract",
        "list_outbound_allowlist_tls_readiness_contracts",
        "normalize_outbound_allowlist_tls_readiness_id",
        "validate_outbound_allowlist_tls_readiness_contracts",
        "validate_outbound_allowlist_tls_readiness_registry",
    }

    assert set(module.__all__) == expected

    for name in expected:
        assert getattr(module, name) is not None
def test_package_exports_r3a_public_surface() -> None:
    import processual_api.integrations as package

    expected = {
        "OUTBOUND_ALLOWLIST_TLS_READINESS_CONTRACTS",
        "SUPPORTED_OUTBOUND_ALLOWLIST_TLS_READINESS",
        "OutboundAllowlistTlsReadinessAssessment",
        "OutboundAllowlistTlsReadinessContract",
        "OutboundAllowlistTlsReadinessStatus",
        "OutboundAllowlistTlsReferenceSubmission",
        "TlsMinimumVersion",
        "assess_outbound_allowlist_tls_readiness",
        "get_outbound_allowlist_tls_readiness_contract",
        "list_outbound_allowlist_tls_readiness_contracts",
        "normalize_outbound_allowlist_tls_readiness_id",
        "validate_outbound_allowlist_tls_readiness_contracts",
        "validate_outbound_allowlist_tls_readiness_registry",
    }

    assert expected.issubset(set(package.__all__))

    for name in expected:
        assert getattr(package, name) is not None


def test_r3a_documentation_records_safety_markers() -> None:
    document = Path(
        "docs/integrations/EXTERNAL_CONNECTIVITY_16F_R3A.md"
    ).read_text(encoding="utf-8")
    lowered = document.lower()

    required_markers = (
        "reference_only_readiness",
        "pending_network_policy_references",
        "network_policy_references_received_for_review",
        "allowlist_reference",
        "host_reference",
        "dns_policy_reference",
        "port_policy_reference",
        "ca_policy_reference",
        "certificate_pinning_policy_reference",
        "proxy_policy_reference",
        "egress_authorization_reference",
        "security_review_reference",
        "operator_approval_reference",
        "kill_switch_reference",
        "tls_1_2",
        "tls_1_3",
        "allowlist_applied",
        "dns_resolution_performed",
        "tls_context_created",
        "certificate_loaded",
        "certificate_pin_applied",
        "proxy_configured",
        "egress_authorized",
        "connection_attempted",
        "external_http_enabled",
        "socket_access_enabled",
        "runtime_enabled",
        "production_allowed",
        "automatic_activation_allowed",
        "performs no dns resolution",
        "opens no socket",
        "performs no external http",
        "authorizes no production use",
    )

    for marker in required_markers:
        assert marker in lowered
