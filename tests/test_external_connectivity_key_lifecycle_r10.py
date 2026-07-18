from __future__ import annotations

import json
from pathlib import Path

import pytest

from processual_api.integrations.connector_bindings import (
    ConnectorEnvironmentBinding,
    get_connector_secret_reference,
    list_connector_environment_bindings,
)
from processual_api.integrations.external_connectivity_cases import (
    ExternalConnectivityCaseState,
    ExternalConnectivityQualificationKeyStatus,
    ExternalConnectivitySandboxApiKeyStatus,
    SupervisorReadinessDecision,
)
from processual_api.schemas.external_connectivity import (
    CustomerReferencePackageSubmissionRequest,
    ExternalConnectivityCaseCreateRequest,
)
from processual_api.services.external_connectivity_case_store import (
    load_external_connectivity_case_store,
)
from processual_api.services.external_connectivity_intake import (
    create_external_connectivity_case,
    get_external_connectivity_case,
    record_external_connectivity_supervisor_decision,
    review_external_connectivity_reference_package,
    submit_external_connectivity_reference_package,
)
from processual_api.services.external_connectivity_qualification import (
    ExternalConnectivityQualificationError,
    issue_external_connectivity_qualification_key,
    issue_external_connectivity_sandbox_api_key,
    redeem_external_connectivity_qualification_key,
    revoke_external_connectivity_qualification_key,
    revoke_external_connectivity_sandbox_api_key,
    suspend_external_connectivity_sandbox_api_key,
)

CREATED_AT = "2026-07-14T10:00:00+00:00"
SUBMITTED_AT = "2026-07-14T10:01:00+00:00"
REVIEWED_AT = "2026-07-14T10:02:00+00:00"
APPROVED_AT = "2026-07-14T10:03:00+00:00"
ATTESTATION_EXPIRES_AT = "2026-07-15T10:03:00+00:00"
QUALIFICATION_ISSUED_AT = "2026-07-14T10:04:00+00:00"
QUALIFICATION_EXPIRES_AT = "2026-07-15T10:00:00+00:00"
QUALIFICATION_REDEEMED_AT = "2026-07-14T10:05:00+00:00"
SANDBOX_ISSUED_AT = "2026-07-14T10:06:00+00:00"
SANDBOX_EXPIRES_AT = "2026-07-15T10:00:00+00:00"
SANDBOX_SUSPENDED_AT = "2026-07-14T10:07:00+00:00"
SANDBOX_REVOKED_AT = "2026-07-14T10:08:00+00:00"

ACTOR = "supsk_r10_supervisor"
CLIENT_ID = "client_r10"
CASE_ID = "case_r10"
QUALIFICATION_KEY_ID = "qk_r10_reference"
SANDBOX_API_KEY_ID = "sbk_r10_reference"


def _sandbox_binding() -> ConnectorEnvironmentBinding:
    return next(
        binding
        for binding in list_connector_environment_bindings()
        if binding.environment == "sandbox"
    )


def _create_request() -> ExternalConnectivityCaseCreateRequest:
    binding = _sandbox_binding()
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )

    return ExternalConnectivityCaseCreateRequest(
        client_id=CLIENT_ID,
        readiness_case_id="readiness_case_r10",
        connector_id=binding.connector_id,
        credential_profile_id=(
            secret_reference.credential_profile_id
        ),
        target_environment="sandbox",
    )


def _submission() -> CustomerReferencePackageSubmissionRequest:
    binding = _sandbox_binding()
    secret_reference = get_connector_secret_reference(
        binding.secret_reference_ids[0]
    )

    return CustomerReferencePackageSubmissionRequest(
        package_id="package_r10",
        client_id=CLIENT_ID,
        schema_version="customer-reference-package/v1",
        connector_id=binding.connector_id,
        credential_profile_id=(
            secret_reference.credential_profile_id
        ),
        target_environment="sandbox",
        target_reference_id=binding.target_reference_id,
        secret_reference_ids=binding.secret_reference_ids,
        dns_reference="dns_reference_r10",
        tls_policy_reference="tls_policy_reference_r10",
        certificate_reference="certificate_reference_r10",
        outbound_allowlist_reference=(
            "outbound_allowlist_reference_r10"
        ),
        submitted_at=SUBMITTED_AT,
    )


def _approved_store(store: Path) -> None:
    create_external_connectivity_case(
        _create_request(),
        case_id=CASE_ID,
        actor=ACTOR,
        occurred_at=CREATED_AT,
        path=store,
    )

    submit_external_connectivity_reference_package(
        CASE_ID,
        _submission(),
        expected_revision=1,
        actor=ACTOR,
        occurred_at=SUBMITTED_AT,
        path=store,
    )

    assessment = review_external_connectivity_reference_package(
        CASE_ID,
        assessment_id="assessment_r10",
        expected_revision=2,
        actor=ACTOR,
        occurred_at=REVIEWED_AT,
        path=store,
    )

    ready_case = get_external_connectivity_case(
        CASE_ID,
        path=store,
    )

    record_external_connectivity_supervisor_decision(
        CASE_ID,
        decision=SupervisorReadinessDecision.APPROVED,
        attestation_id="attestation_r10",
        expected_revision=ready_case.revision,
        expected_package_fingerprint=(
            assessment.customer_package_fingerprint
        ),
        actor=ACTOR,
        reason_code="readiness_review_completed",
        occurred_at=APPROVED_AT,
        expires_at=ATTESTATION_EXPIRES_AT,
        path=store,
    )


def _issue_qualification(store: Path) -> dict[str, object]:
    case = get_external_connectivity_case(
        CASE_ID,
        path=store,
    )

    return issue_external_connectivity_qualification_key(
        CASE_ID,
        qualification_key_id=QUALIFICATION_KEY_ID,
        expected_revision=case.revision,
        actor=ACTOR,
        occurred_at=QUALIFICATION_ISSUED_AT,
        expires_at=QUALIFICATION_EXPIRES_AT,
        path=store,
    )


def _redeem_qualification(
    store: Path,
    raw_key: str,
) -> dict[str, object]:
    case = get_external_connectivity_case(
        CASE_ID,
        path=store,
    )

    return redeem_external_connectivity_qualification_key(
        raw_key,
        client_id=CLIENT_ID,
        redeemed_by="client_user_r10",
        expected_revision=case.revision,
        occurred_at=QUALIFICATION_REDEEMED_AT,
        path=store,
    )


def _issue_sandbox_key(store: Path) -> dict[str, object]:
    from processual_api.integrations.connector_registry import (
        get_runtime_connector_contract,
    )

    case = get_external_connectivity_case(
        CASE_ID,
        path=store,
    )
    contract = get_runtime_connector_contract(
        case.connector_id
    )
    allowed_scope_id = contract.capabilities[0].scope_id

    return issue_external_connectivity_sandbox_api_key(
        CASE_ID,
        sandbox_api_key_id=SANDBOX_API_KEY_ID,
        allowed_scope_ids=(allowed_scope_id,),
        expected_revision=case.revision,
        actor=ACTOR,
        occurred_at=SANDBOX_ISSUED_AT,
        expires_at=SANDBOX_EXPIRES_AT,
        path=store,
    )


def test_r10_complete_key_lifecycle_is_canonical_and_default_deny(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)

    issued = _issue_qualification(store)
    raw_qualification_key = str(
        issued["qualification_key_once"]
    )

    assert issued["raw_qualification_key_visible_once"] is True
    assert issued["case"].state is (
        ExternalConnectivityCaseState.QUALIFICATION_KEY_ISSUED
    )
    assert issued["case"].revision == 6
    assert "key_hash" not in issued["qualification_key"]
    assert json.dumps(
        issued,
        default=str,
    ).count(raw_qualification_key) == 1
    assert raw_qualification_key not in store.read_text(
        encoding="utf-8"
    )

    redeemed = _redeem_qualification(
        store,
        raw_qualification_key,
    )

    assert redeemed["case"].state is (
        ExternalConnectivityCaseState.QUALIFICATION_REDEEMED
    )
    assert redeemed["case"].revision == 7
    assert redeemed["qualification_key"]["status"] == "redeemed"
    assert raw_qualification_key not in json.dumps(
        redeemed,
        default=str,
    )
    assert raw_qualification_key not in store.read_text(
        encoding="utf-8"
    )

    sandbox_issued = _issue_sandbox_key(store)
    raw_sandbox_key = str(
        sandbox_issued["sandbox_api_key_once"]
    )

    assert sandbox_issued["raw_sandbox_api_key_visible_once"] is True
    assert sandbox_issued["case"].state is (
        ExternalConnectivityCaseState.SANDBOX_API_KEY_ISSUED
    )
    assert sandbox_issued["case"].revision == 8
    assert "key_hash" not in sandbox_issued["sandbox_api_key"]
    assert json.dumps(
        sandbox_issued,
        default=str,
    ).count(raw_sandbox_key) == 1
    assert raw_sandbox_key not in store.read_text(
        encoding="utf-8"
    )

    suspended = suspend_external_connectivity_sandbox_api_key(
        SANDBOX_API_KEY_ID,
        case_id=CASE_ID,
        expected_revision=8,
        actor=ACTOR,
        occurred_at=SANDBOX_SUSPENDED_AT,
        path=store,
    )

    assert suspended["sandbox_api_key"]["status"] == "suspended"
    assert suspended["case"].state is (
        ExternalConnectivityCaseState.SANDBOX_API_KEY_ISSUED
    )
    assert suspended["case"].revision == 9

    revoked = revoke_external_connectivity_sandbox_api_key(
        SANDBOX_API_KEY_ID,
        case_id=CASE_ID,
        expected_revision=9,
        actor=ACTOR,
        occurred_at=SANDBOX_REVOKED_AT,
        path=store,
    )

    assert revoked["sandbox_api_key"]["status"] == "revoked"
    assert revoked["case"].state is (
        ExternalConnectivityCaseState.SANDBOX_REVOKED
    )
    assert revoked["case"].revision == 10

    snapshot = load_external_connectivity_case_store(store)

    assert len(snapshot.qualification_keys) == 1
    assert len(snapshot.sandbox_api_keys) == 1
    assert snapshot.qualification_keys[0].status is (
        ExternalConnectivityQualificationKeyStatus.REDEEMED
    )
    assert snapshot.sandbox_api_keys[0].status is (
        ExternalConnectivitySandboxApiKeyStatus.REVOKED
    )
    assert snapshot.qualification_keys[0].key_hash
    assert snapshot.sandbox_api_keys[0].key_hash
    assert raw_qualification_key not in store.read_text(
        encoding="utf-8"
    )
    assert raw_sandbox_key not in store.read_text(
        encoding="utf-8"
    )


def test_r10_second_qualification_issuance_is_side_effect_free(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    _issue_qualification(store)

    case = get_external_connectivity_case(CASE_ID, path=store)
    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="qualification_key_issuance_not_allowed",
    ):
        issue_external_connectivity_qualification_key(
            CASE_ID,
            qualification_key_id="qk_r10_second",
            expected_revision=case.revision,
            actor=ACTOR,
            occurred_at="2026-07-14T10:04:30+00:00",
            expires_at=QUALIFICATION_EXPIRES_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_redemption_rejects_wrong_client_invalid_key_and_stale_revision(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    issued = _issue_qualification(store)
    raw_key = str(issued["qualification_key_once"])
    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="qualification_key_client_mismatch",
    ):
        redeem_external_connectivity_qualification_key(
            raw_key,
            client_id="wrong_client",
            redeemed_by="client_user_r10",
            expected_revision=6,
            occurred_at=QUALIFICATION_REDEEMED_AT,
            path=store,
        )

    assert store.read_bytes() == before

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="qualification_key_invalid",
    ):
        redeem_external_connectivity_qualification_key(
            "qk_invalid.invalid-secret",
            client_id=CLIENT_ID,
            redeemed_by="client_user_r10",
            expected_revision=6,
            occurred_at=QUALIFICATION_REDEEMED_AT,
            path=store,
        )

    assert store.read_bytes() == before

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="case_revision_conflict",
    ):
        redeem_external_connectivity_qualification_key(
            raw_key,
            client_id=CLIENT_ID,
            redeemed_by="client_user_r10",
            expected_revision=5,
            occurred_at=QUALIFICATION_REDEEMED_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_expired_qualification_key_cannot_be_redeemed(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)

    case = get_external_connectivity_case(CASE_ID, path=store)
    issued = issue_external_connectivity_qualification_key(
        CASE_ID,
        qualification_key_id=QUALIFICATION_KEY_ID,
        expected_revision=case.revision,
        actor=ACTOR,
        occurred_at=QUALIFICATION_ISSUED_AT,
        expires_at="2026-07-14T10:04:30+00:00",
        path=store,
    )

    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="qualification_key_expired",
    ):
        redeem_external_connectivity_qualification_key(
            str(issued["qualification_key_once"]),
            client_id=CLIENT_ID,
            redeemed_by="client_user_r10",
            expected_revision=6,
            occurred_at=QUALIFICATION_REDEEMED_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_qualification_key_is_strictly_one_time(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    issued = _issue_qualification(store)
    raw_key = str(issued["qualification_key_once"])
    _redeem_qualification(store, raw_key)

    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="qualification_key_already_redeemed",
    ):
        redeem_external_connectivity_qualification_key(
            raw_key,
            client_id=CLIENT_ID,
            redeemed_by="client_user_r10",
            expected_revision=7,
            occurred_at="2026-07-14T10:05:30+00:00",
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_sandbox_api_key_second_issuance_is_side_effect_free(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    issued = _issue_qualification(store)
    _redeem_qualification(
        store,
        str(issued["qualification_key_once"]),
    )
    _issue_sandbox_key(store)

    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="sandbox_api_key_issuance_not_allowed",
    ):
        issue_external_connectivity_sandbox_api_key(
            CASE_ID,
            sandbox_api_key_id="sbk_r10_second",
            allowed_scope_ids=("ticketing:read",),
            expected_revision=8,
            actor=ACTOR,
            occurred_at="2026-07-14T10:06:30+00:00",
            expires_at=SANDBOX_EXPIRES_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_qualification_revocation_blocks_redemption(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    issued = _issue_qualification(store)
    raw_key = str(issued["qualification_key_once"])

    revoked = revoke_external_connectivity_qualification_key(
        QUALIFICATION_KEY_ID,
        case_id=CASE_ID,
        expected_revision=6,
        actor=ACTOR,
        occurred_at="2026-07-14T10:04:30+00:00",
        path=store,
    )

    assert revoked["qualification_key"]["status"] == "revoked"
    assert revoked["case"].state is (
        ExternalConnectivityCaseState.SANDBOX_REVOKED
    )

    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="qualification_key_revoked",
    ):
        redeem_external_connectivity_qualification_key(
            raw_key,
            client_id=CLIENT_ID,
            redeemed_by="client_user_r10",
            expected_revision=7,
            occurred_at=QUALIFICATION_REDEEMED_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_expired_attestation_blocks_qualification_issuance(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match=(
            "current_supervisor_readiness_"
            "attestation_required"
        ),
    ):
        issue_external_connectivity_qualification_key(
            CASE_ID,
            qualification_key_id=QUALIFICATION_KEY_ID,
            expected_revision=5,
            actor=ACTOR,
            occurred_at="2026-07-15T10:04:00+00:00",
            expires_at="2026-07-15T11:04:00+00:00",
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_rejects_scope_outside_connector_contract(
    tmp_path: Path,
) -> None:
    from processual_api.integrations.connector_registry import (
        get_runtime_connector_contract,
    )
    from processual_api.integrations.scope_catalog import (
        list_integration_scopes,
    )

    store = tmp_path / "cases.json"
    _approved_store(store)

    issued = _issue_qualification(store)
    _redeem_qualification(
        store,
        str(issued["qualification_key_once"]),
    )

    case = get_external_connectivity_case(
        CASE_ID,
        path=store,
    )
    contract = get_runtime_connector_contract(
        case.connector_id
    )
    connector_scope_ids = {
        capability.scope_id
        for capability in contract.capabilities
    }
    foreign_scope_id = next(
        scope.scope_id
        for scope in list_integration_scopes()
        if scope.scope_id not in connector_scope_ids
    )

    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="sandbox_scope_not_allowed_for_connector",
    ):
        issue_external_connectivity_sandbox_api_key(
            CASE_ID,
            sandbox_api_key_id="sbk_r10_foreign_scope",
            allowed_scope_ids=(foreign_scope_id,),
            expected_revision=case.revision,
            actor=ACTOR,
            occurred_at=SANDBOX_ISSUED_AT,
            expires_at=SANDBOX_EXPIRES_AT,
            path=store,
        )

    assert store.read_bytes() == before


def test_r10_qualification_revoke_rejects_case_id_mismatch(
    tmp_path: Path,
) -> None:
    store = tmp_path / "cases.json"
    _approved_store(store)
    _issue_qualification(store)

    before = store.read_bytes()

    with pytest.raises(
        ExternalConnectivityQualificationError,
        match="external_connectivity_case_mismatch",
    ):
        revoke_external_connectivity_qualification_key(
            QUALIFICATION_KEY_ID,
            case_id="different_case_r10",
            expected_revision=6,
            actor=ACTOR,
            occurred_at="2026-07-14T10:04:30+00:00",
            path=store,
        )

    assert store.read_bytes() == before
