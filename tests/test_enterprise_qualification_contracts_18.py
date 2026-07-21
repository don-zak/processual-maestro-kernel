from datetime import UTC, datetime, timedelta

from processual_api.integrations.credential_profiles import get_credential_profile
from processual_api.services.enterprise_qualification_18 import (
    QualificationGrant,
    TaskCredentialRecord,
    executable_task_ids,
    get_task_execution_policy,
    safe_grant_projection,
    safe_task_credential_projection,
    task_credential_eligibility,
)


def _grant(
    *,
    case_id: str = "icase_demo",
    client_id: str = "client_demo",
    track: str = "camara",
    approved_task_ids: tuple[str, ...] = (
        "sandbox_capability_probe",
    ),
    status: str = "approved",
) -> QualificationGrant:
    now = datetime.now(UTC)

    return QualificationGrant(
        grant_id="qgrant_demo",
        case_id=case_id,
        client_id=client_id,
        integration_track=track,
        approved_task_ids=approved_task_ids,
        approved_profile_ids=(
            "telecom_operations_api_reference",
        ),
        issued_by_supervisor_id="supervisor_demo",
        supervisor_session_key_id="supsk_internal",
        issued_at=now.isoformat(),
        expires_at=(
            now + timedelta(days=7)
        ).isoformat(),
        status=status,
    )


def _case(
    *,
    case_id: str = "icase_demo",
    client_id: str = "client_demo",
    track: str = "camara",
    status: str = "ready_for_review",
) -> dict:
    return {
        "case_id": case_id,
        "client_id": client_id,
        "integration_track": track,
        "status": status,
    }


def test_only_explicit_operational_tasks_are_executable() -> None:
    assert executable_task_ids("camara") == (
        "sandbox_capability_probe",
    )

    assert executable_task_ids("tmforum") == (
        "ctk_contract_probe",
    )

    assert executable_task_ids("operator") == ()

    reference_policy = get_task_execution_policy(
        "camara",
        "consent_reference",
    )

    assert reference_policy.executable is False
    assert reference_policy.credential_profile_id is None


def test_unknown_task_is_default_denied() -> None:
    policy = get_task_execution_policy(
        "camara",
        "unknown_task",
    )

    assert policy.executable is False
    assert policy.requires_qualification is True
    assert policy.production_allowed is False
    assert policy.runtime_connector_approved is False
    assert policy.external_http_allowed is False
    assert policy.raw_secret_visible is False


def test_missing_grant_denies_task_credential() -> None:
    result = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=None,
    )

    assert result["eligible"] is False
    assert result["credential_status"] == "not_eligible"
    assert "qualification_grant_missing" in result["blockers"]
    assert result["production_allowed"] is False
    assert result["runtime_connector_approved"] is False
    assert result["raw_secret_visible"] is False


def test_reference_task_never_receives_credential() -> None:
    result = task_credential_eligibility(
        case=_case(),
        task_id="consent_reference",
        grant=_grant(
            approved_task_ids=("consent_reference",),
        ),
    )

    assert result["eligible"] is False
    assert "task_not_executable" in result["blockers"]
    assert result["operational_profile_id"] is None


def test_validated_case_and_matching_grant_allow_eligibility() -> None:
    result = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=_grant(),
    )

    assert result["eligible"] is True
    assert result["credential_status"] == "eligible"
    assert result["blockers"] == []

    assert (
        result["operational_profile_id"]
        == "enterprise_telecom_conformance_read"
    )
    assert (
        result["credential_profile_id"]
        == "telecom_operations_api_reference"
    )
    assert result["connector_id"] == "telecom_crm_reference"
    assert result["allowed_scope_ids"] == ["crm:read"]

    assert result["environment"] == "sandbox"
    assert result["read_only"] is True
    assert result["write_allowed"] is False
    assert result["production_allowed"] is False
    assert result["runtime_connector_approved"] is False
    assert result["external_http_allowed"] is False


def test_case_client_and_track_mismatches_are_denied() -> None:
    wrong_case = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=_grant(case_id="other_case"),
    )

    assert wrong_case["eligible"] is False
    assert "grant_case_mismatch" in wrong_case["blockers"]

    wrong_client = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=_grant(client_id="other_client"),
    )

    assert wrong_client["eligible"] is False
    assert "grant_client_mismatch" in wrong_client["blockers"]

    wrong_track = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=_grant(track="operator"),
    )

    assert wrong_track["eligible"] is False
    assert "grant_track_mismatch" in wrong_track["blockers"]


def test_inactive_or_unapproved_grant_is_denied() -> None:
    revoked = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=_grant(status="revoked"),
    )

    assert revoked["eligible"] is False
    assert (
        "qualification_grant_inactive"
        in revoked["blockers"]
    )

    unapproved = task_credential_eligibility(
        case=_case(),
        task_id="sandbox_capability_probe",
        grant=_grant(approved_task_ids=()),
    )

    assert unapproved["eligible"] is False
    assert "task_not_approved" in unapproved["blockers"]


def test_unvalidated_case_is_denied() -> None:
    result = task_credential_eligibility(
        case=_case(status="in_progress"),
        task_id="sandbox_capability_probe",
        grant=_grant(),
    )

    assert result["eligible"] is False
    assert "case_not_validated" in result["blockers"]


def test_safe_grant_projection_removes_session_authority() -> None:
    projection = safe_grant_projection(_grant())

    assert "supervisor_session_key_id" not in projection
    assert projection["production_allowed"] is False
    assert (
        projection["runtime_connector_approved"]
        is False
    )
    assert projection["raw_secret_visible"] is False
    assert projection["external_http_allowed"] is False


def test_safe_task_credential_projection_never_contains_raw_key() -> None:
    now = datetime.now(UTC)

    credential = TaskCredentialRecord(
        key_id="taskkey_demo",
        case_id="icase_demo",
        task_id="sandbox_capability_probe",
        client_id="client_demo",
        qualification_grant_id="qgrant_demo",
        operational_profile_id=(
            "telecom_operations_api_reference"
        ),
        issued_at=now.isoformat(),
        expires_at=(
            now + timedelta(days=7)
        ).isoformat(),
    )

    projection = safe_task_credential_projection(
        credential
    )

    assert "api_key" not in projection
    assert "raw_key" not in projection
    assert "hashed" not in projection

    assert projection["production_allowed"] is False
    assert (
        projection["runtime_connector_approved"]
        is False
    )
    assert projection["write_allowed"] is False
    assert projection["raw_secret_visible"] is False


def test_executable_task_profiles_exist_in_registered_catalog() -> None:
    for track in ("camara", "tmforum", "operator"):
        for task_id in executable_task_ids(track):
            policy = get_task_execution_policy(
                track,
                task_id,
            )

            profile = get_credential_profile(
                str(policy.credential_profile_id or "")
            )

            assert (
                profile.credential_profile_id
                == "telecom_operations_api_reference"
            )
            assert profile.approved_for_runtime is False
            assert profile.runtime_connector_approved is False
