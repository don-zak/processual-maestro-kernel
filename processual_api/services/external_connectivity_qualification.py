from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
)
from processual_api.integrations.external_connectivity_cases import (
    ExternalConnectivityCase,
    ExternalConnectivityCaseState,
    ExternalConnectivityQualificationKey,
    ExternalConnectivityQualificationKeyStatus,
    ExternalConnectivitySandboxApiKey,
    ExternalConnectivitySandboxApiKeyStatus,
    SupervisorReadinessAttestation,
    advance_external_connectivity_case,
    is_supervisor_readiness_attestation_current,
)
from processual_api.services.external_connectivity_case_store import (
    ExternalConnectivityCaseStoreSnapshot,
    load_external_connectivity_case_store,
    save_external_connectivity_case_store,
)

EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION: Final = (
    "external-connectivity-qualification/v1"
)


class ExternalConnectivityQualificationError(ValueError):
    pass


def _require_identifier(field_name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExternalConnectivityQualificationError(
            f"{field_name}_required"
        )
    return value.strip()


def _parse_time(field_name: str, value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ExternalConnectivityQualificationError(
            f"{field_name}_required"
        )

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ExternalConnectivityQualificationError(
            f"{field_name}_invalid"
        ) from exc

    if parsed.tzinfo is None:
        raise ExternalConnectivityQualificationError(
            f"{field_name}_timezone_required"
        )

    return parsed.astimezone(UTC)


def _require_time_window(
    occurred_at: str,
    expires_at: str,
) -> None:
    occurred = _parse_time("occurred_at", occurred_at)
    expires = _parse_time("expires_at", expires_at)

    if expires <= occurred:
        raise ExternalConnectivityQualificationError(
            "expires_at_must_follow_occurred_at"
        )


def _key_hash(raw_key: str) -> str:
    return hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()


def _new_raw_key(key_id: str) -> str:
    return f"{key_id}.{secrets.token_urlsafe(32)}"


def _require_case_binding(
    requested_case_id: str,
    bound_case_id: str,
) -> None:
    requested = _require_identifier(
        "case_id",
        requested_case_id,
    )

    if requested != bound_case_id:
        raise ExternalConnectivityQualificationError(
            "external_connectivity_case_mismatch"
        )


def _validated_connector_scope_ids(
    case: ExternalConnectivityCase,
    allowed_scope_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if not isinstance(allowed_scope_ids, (tuple, list)):
        raise ExternalConnectivityQualificationError(
            "sandbox_scope_ids_invalid"
        )

    normalized = tuple(
        _require_identifier(
            "allowed_scope_id",
            scope_id,
        ).lower()
        for scope_id in allowed_scope_ids
    )

    if not normalized:
        raise ExternalConnectivityQualificationError(
            "sandbox_scope_ids_required"
        )

    if len(set(normalized)) != len(normalized):
        raise ExternalConnectivityQualificationError(
            "sandbox_scope_ids_duplicate"
        )

    try:
        contract = get_runtime_connector_contract(
            case.connector_id
        )
    except ValueError as exc:
        raise ExternalConnectivityQualificationError(
            "external_connectivity_connector_not_supported"
        ) from exc

    connector_scope_ids = {
        capability.scope_id
        for capability in contract.capabilities
    }

    if not set(normalized).issubset(connector_scope_ids):
        raise ExternalConnectivityQualificationError(
            "sandbox_scope_not_allowed_for_connector"
        )

    return normalized


def _case_by_id(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    case_id: str,
) -> ExternalConnectivityCase:
    for case in snapshot.cases:
        if case.case_id == case_id:
            return case

    raise ExternalConnectivityQualificationError(
        "external_connectivity_case_not_found"
    )


def _require_revision(
    case: ExternalConnectivityCase,
    expected_revision: int,
) -> None:
    if (
        not isinstance(expected_revision, int)
        or expected_revision < 1
        or case.revision != expected_revision
    ):
        raise ExternalConnectivityQualificationError(
            "case_revision_conflict"
        )


def _replace_case(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    updated_case: ExternalConnectivityCase,
) -> ExternalConnectivityCaseStoreSnapshot:
    return replace(
        snapshot,
        cases=tuple(
            updated_case
            if case.case_id == updated_case.case_id
            else case
            for case in snapshot.cases
        ),
    )


def _touch_case(
    case: ExternalConnectivityCase,
    *,
    occurred_at: str,
) -> ExternalConnectivityCase:
    return replace(
        case,
        revision=case.revision + 1,
        updated_at=occurred_at,
    )


def _current_attestation(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    case: ExternalConnectivityCase,
    *,
    checked_at: str,
) -> SupervisorReadinessAttestation:
    matches = tuple(
        attestation
        for attestation in (
            snapshot.supervisor_readiness_attestations
        )
        if is_supervisor_readiness_attestation_current(
            attestation,
            case,
            checked_at=checked_at,
        )
    )

    if not matches:
        raise ExternalConnectivityQualificationError(
            "current_supervisor_readiness_attestation_required"
        )

    return sorted(
        matches,
        key=lambda item: item.issued_at,
    )[-1]


def _qualification_key_by_id(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    qualification_key_id: str,
) -> ExternalConnectivityQualificationKey:
    for qualification_key in snapshot.qualification_keys:
        if (
            qualification_key.qualification_key_id
            == qualification_key_id
        ):
            return qualification_key

    raise ExternalConnectivityQualificationError(
        "qualification_key_not_found"
    )


def _qualification_key_by_raw_value(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    raw_qualification_key: str,
) -> ExternalConnectivityQualificationKey:
    candidate_hash = _key_hash(raw_qualification_key)

    for qualification_key in snapshot.qualification_keys:
        if hmac.compare_digest(
            qualification_key.key_hash,
            candidate_hash,
        ):
            return qualification_key

    raise ExternalConnectivityQualificationError(
        "qualification_key_invalid"
    )


def _sandbox_api_key_by_id(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    sandbox_api_key_id: str,
) -> ExternalConnectivitySandboxApiKey:
    for sandbox_api_key in snapshot.sandbox_api_keys:
        if (
            sandbox_api_key.sandbox_api_key_id
            == sandbox_api_key_id
        ):
            return sandbox_api_key

    raise ExternalConnectivityQualificationError(
        "sandbox_api_key_not_found"
    )


def _replace_qualification_key(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    updated_key: ExternalConnectivityQualificationKey,
) -> ExternalConnectivityCaseStoreSnapshot:
    return replace(
        snapshot,
        qualification_keys=tuple(
            updated_key
            if (
                key.qualification_key_id
                == updated_key.qualification_key_id
            )
            else key
            for key in snapshot.qualification_keys
        ),
    )


def _replace_sandbox_api_key(
    snapshot: ExternalConnectivityCaseStoreSnapshot,
    updated_key: ExternalConnectivitySandboxApiKey,
) -> ExternalConnectivityCaseStoreSnapshot:
    return replace(
        snapshot,
        sandbox_api_keys=tuple(
            updated_key
            if (
                key.sandbox_api_key_id
                == updated_key.sandbox_api_key_id
            )
            else key
            for key in snapshot.sandbox_api_keys
        ),
    )


def _qualification_key_projection(
    qualification_key: ExternalConnectivityQualificationKey,
) -> dict[str, Any]:
    payload = asdict(qualification_key)
    payload.pop("key_hash", None)
    payload["status"] = qualification_key.status.value
    return payload


def _sandbox_api_key_projection(
    sandbox_api_key: ExternalConnectivitySandboxApiKey,
) -> dict[str, Any]:
    payload = asdict(sandbox_api_key)
    payload.pop("key_hash", None)
    payload["status"] = sandbox_api_key.status.value
    payload["allowed_scope_ids"] = list(
        sandbox_api_key.allowed_scope_ids
    )
    return payload


def _result_guardrails() -> dict[str, bool]:
    return {
        "runtime_connector_allowed": False,
        "production_allowed": False,
        "external_http_allowed": False,
        "secret_resolution_allowed": False,
        "automatic_activation_allowed": False,
        "raw_secret_visible": False,
    }


def issue_external_connectivity_qualification_key(
    case_id: str,
    *,
    qualification_key_id: str,
    expected_revision: int,
    actor: str,
    occurred_at: str,
    expires_at: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    _require_identifier("case_id", case_id)
    _require_identifier(
        "qualification_key_id",
        qualification_key_id,
    )
    actor = _require_identifier("actor", actor)
    _require_time_window(occurred_at, expires_at)

    snapshot = load_external_connectivity_case_store(path)
    case = _case_by_id(snapshot, case_id)
    _require_revision(case, expected_revision)

    if (
        case.state
        is not ExternalConnectivityCaseState.READINESS_APPROVED
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_issuance_not_allowed"
        )

    if any(
        key.case_id == case.case_id
        for key in snapshot.qualification_keys
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_already_issued"
        )

    attestation = _current_attestation(
        snapshot,
        case,
        checked_at=occurred_at,
    )

    if (
        _parse_time("expires_at", expires_at)
        > _parse_time(
            "attestation_expires_at",
            attestation.expires_at,
        )
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_exceeds_attestation_expiry"
        )

    raw_key = _new_raw_key(qualification_key_id)

    qualification_key = ExternalConnectivityQualificationKey(
        qualification_key_id=qualification_key_id,
        case_id=case.case_id,
        client_id=case.client_id,
        attestation_id=attestation.attestation_id,
        readiness_assessment_id=(
            attestation.readiness_assessment_id
        ),
        customer_package_fingerprint=(
            attestation.customer_package_fingerprint
        ),
        key_hash=_key_hash(raw_key),
        status=ExternalConnectivityQualificationKeyStatus.ISSUED,
        issued_at=occurred_at,
        expires_at=expires_at,
        issued_by=actor,
    )

    updated_case = advance_external_connectivity_case(
        case,
        target_state=(
            ExternalConnectivityCaseState
            .QUALIFICATION_KEY_ISSUED
        ),
        updated_at=occurred_at,
    )

    updated = _replace_case(snapshot, updated_case)
    updated = replace(
        updated,
        qualification_keys=(
            *updated.qualification_keys,
            qualification_key,
        ),
    )
    save_external_connectivity_case_store(updated, path)

    return {
        "schema_version": (
            EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION
        ),
        "qualification_key_once": raw_key,
        "raw_qualification_key_visible_once": True,
        "qualification_key": _qualification_key_projection(
            qualification_key
        ),
        "case": updated_case,
        "guardrails": _result_guardrails(),
    }


def redeem_external_connectivity_qualification_key(
    raw_qualification_key: str,
    *,
    client_id: str,
    redeemed_by: str,
    expected_revision: int,
    occurred_at: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    raw_qualification_key = _require_identifier(
        "raw_qualification_key",
        raw_qualification_key,
    )
    client_id = _require_identifier("client_id", client_id)
    redeemed_by = _require_identifier(
        "redeemed_by",
        redeemed_by,
    )
    occurred = _parse_time("occurred_at", occurred_at)

    snapshot = load_external_connectivity_case_store(path)
    qualification_key = _qualification_key_by_raw_value(
        snapshot,
        raw_qualification_key,
    )
    case = _case_by_id(snapshot, qualification_key.case_id)
    _require_revision(case, expected_revision)

    if client_id != qualification_key.client_id:
        raise ExternalConnectivityQualificationError(
            "qualification_key_client_mismatch"
        )

    if (
        qualification_key.status
        is ExternalConnectivityQualificationKeyStatus.REVOKED
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_revoked"
        )

    if (
        qualification_key.status
        is ExternalConnectivityQualificationKeyStatus.REDEEMED
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_already_redeemed"
        )

    if (
        qualification_key.status
        is ExternalConnectivityQualificationKeyStatus.EXPIRED
        or occurred
        >= _parse_time(
            "qualification_key_expires_at",
            qualification_key.expires_at,
        )
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_expired"
        )

    if (
        case.state
        is not ExternalConnectivityCaseState.QUALIFICATION_KEY_ISSUED
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_redemption_not_allowed"
        )

    redeemed_key = replace(
        qualification_key,
        status=(
            ExternalConnectivityQualificationKeyStatus.REDEEMED
        ),
        redeemed_at=occurred_at,
        redeemed_by=redeemed_by,
    )

    updated_case = advance_external_connectivity_case(
        case,
        target_state=(
            ExternalConnectivityCaseState.QUALIFICATION_REDEEMED
        ),
        updated_at=occurred_at,
    )

    updated = _replace_qualification_key(
        snapshot,
        redeemed_key,
    )
    updated = _replace_case(updated, updated_case)
    save_external_connectivity_case_store(updated, path)

    return {
        "schema_version": (
            EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION
        ),
        "qualification_key": _qualification_key_projection(
            redeemed_key
        ),
        "case": updated_case,
        "guardrails": _result_guardrails(),
    }


def revoke_external_connectivity_qualification_key(
    qualification_key_id: str,
    *,
    case_id: str,
    expected_revision: int,
    actor: str,
    occurred_at: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    qualification_key_id = _require_identifier(
        "qualification_key_id",
        qualification_key_id,
    )
    actor = _require_identifier("actor", actor)
    _parse_time("occurred_at", occurred_at)

    snapshot = load_external_connectivity_case_store(path)
    qualification_key = _qualification_key_by_id(
        snapshot,
        qualification_key_id,
    )
    _require_case_binding(
        case_id,
        qualification_key.case_id,
    )
    case = _case_by_id(snapshot, qualification_key.case_id)
    _require_revision(case, expected_revision)

    if (
        qualification_key.status
        is ExternalConnectivityQualificationKeyStatus.REVOKED
    ):
        raise ExternalConnectivityQualificationError(
            "qualification_key_already_revoked"
        )

    if snapshot.sandbox_api_keys:
        if any(
            key.case_id == case.case_id
            for key in snapshot.sandbox_api_keys
        ):
            raise ExternalConnectivityQualificationError(
                "revoke_sandbox_api_key_instead"
            )

    revoked_key = replace(
        qualification_key,
        status=(
            ExternalConnectivityQualificationKeyStatus.REVOKED
        ),
        revoked_at=occurred_at,
        revoked_by=actor,
    )

    updated_case = advance_external_connectivity_case(
        case,
        target_state=ExternalConnectivityCaseState.SANDBOX_REVOKED,
        updated_at=occurred_at,
    )

    updated = _replace_qualification_key(
        snapshot,
        revoked_key,
    )
    updated = _replace_case(updated, updated_case)
    save_external_connectivity_case_store(updated, path)

    return {
        "schema_version": (
            EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION
        ),
        "qualification_key": _qualification_key_projection(
            revoked_key
        ),
        "case": updated_case,
        "guardrails": _result_guardrails(),
    }


def issue_external_connectivity_sandbox_api_key(
    case_id: str,
    *,
    sandbox_api_key_id: str,
    allowed_scope_ids: tuple[str, ...],
    expected_revision: int,
    actor: str,
    occurred_at: str,
    expires_at: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    _require_identifier("case_id", case_id)
    _require_identifier(
        "sandbox_api_key_id",
        sandbox_api_key_id,
    )
    actor = _require_identifier("actor", actor)
    _require_time_window(occurred_at, expires_at)

    snapshot = load_external_connectivity_case_store(path)
    case = _case_by_id(snapshot, case_id)
    _require_revision(case, expected_revision)

    if (
        case.state
        is not ExternalConnectivityCaseState.QUALIFICATION_REDEEMED
    ):
        raise ExternalConnectivityQualificationError(
            "sandbox_api_key_issuance_not_allowed"
        )

    if any(
        key.case_id == case.case_id
        for key in snapshot.sandbox_api_keys
    ):
        raise ExternalConnectivityQualificationError(
            "sandbox_api_key_already_issued"
        )

    redeemed_keys = tuple(
        key
        for key in snapshot.qualification_keys
        if (
            key.case_id == case.case_id
            and key.status
            is ExternalConnectivityQualificationKeyStatus.REDEEMED
        )
    )

    if len(redeemed_keys) != 1:
        raise ExternalConnectivityQualificationError(
            "redeemed_qualification_key_required"
        )

    validated_scope_ids = (
        _validated_connector_scope_ids(
            case,
            allowed_scope_ids,
        )
    )

    raw_key = _new_raw_key(sandbox_api_key_id)

    sandbox_api_key = ExternalConnectivitySandboxApiKey(
        sandbox_api_key_id=sandbox_api_key_id,
        case_id=case.case_id,
        client_id=case.client_id,
        qualification_key_id=(
            redeemed_keys[0].qualification_key_id
        ),
        connector_id=case.connector_id,
        credential_profile_id=case.credential_profile_id,
        target_environment=case.target_environment,
        allowed_scope_ids=validated_scope_ids,
        key_hash=_key_hash(raw_key),
        status=ExternalConnectivitySandboxApiKeyStatus.ISSUED,
        issued_at=occurred_at,
        expires_at=expires_at,
        issued_by=actor,
    )

    updated_case = advance_external_connectivity_case(
        case,
        target_state=(
            ExternalConnectivityCaseState.SANDBOX_API_KEY_ISSUED
        ),
        updated_at=occurred_at,
    )

    updated = _replace_case(snapshot, updated_case)
    updated = replace(
        updated,
        sandbox_api_keys=(
            *updated.sandbox_api_keys,
            sandbox_api_key,
        ),
    )
    save_external_connectivity_case_store(updated, path)

    return {
        "schema_version": (
            EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION
        ),
        "sandbox_api_key_once": raw_key,
        "raw_sandbox_api_key_visible_once": True,
        "sandbox_api_key": _sandbox_api_key_projection(
            sandbox_api_key
        ),
        "case": updated_case,
        "guardrails": _result_guardrails(),
    }


def suspend_external_connectivity_sandbox_api_key(
    sandbox_api_key_id: str,
    *,
    case_id: str,
    expected_revision: int,
    actor: str,
    occurred_at: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    sandbox_api_key_id = _require_identifier(
        "sandbox_api_key_id",
        sandbox_api_key_id,
    )
    actor = _require_identifier("actor", actor)
    _parse_time("occurred_at", occurred_at)

    snapshot = load_external_connectivity_case_store(path)
    sandbox_api_key = _sandbox_api_key_by_id(
        snapshot,
        sandbox_api_key_id,
    )
    _require_case_binding(
        case_id,
        sandbox_api_key.case_id,
    )
    case = _case_by_id(snapshot, sandbox_api_key.case_id)
    _require_revision(case, expected_revision)

    if (
        sandbox_api_key.status
        is not ExternalConnectivitySandboxApiKeyStatus.ISSUED
    ):
        raise ExternalConnectivityQualificationError(
            "sandbox_api_key_suspension_not_allowed"
        )

    suspended_key = replace(
        sandbox_api_key,
        status=ExternalConnectivitySandboxApiKeyStatus.SUSPENDED,
        suspended_at=occurred_at,
        suspended_by=actor,
    )
    updated_case = _touch_case(
        case,
        occurred_at=occurred_at,
    )

    updated = _replace_sandbox_api_key(
        snapshot,
        suspended_key,
    )
    updated = _replace_case(updated, updated_case)
    save_external_connectivity_case_store(updated, path)

    return {
        "schema_version": (
            EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION
        ),
        "sandbox_api_key": _sandbox_api_key_projection(
            suspended_key
        ),
        "case": updated_case,
        "guardrails": _result_guardrails(),
    }


def revoke_external_connectivity_sandbox_api_key(
    sandbox_api_key_id: str,
    *,
    case_id: str,
    expected_revision: int,
    actor: str,
    occurred_at: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    sandbox_api_key_id = _require_identifier(
        "sandbox_api_key_id",
        sandbox_api_key_id,
    )
    actor = _require_identifier("actor", actor)
    _parse_time("occurred_at", occurred_at)

    snapshot = load_external_connectivity_case_store(path)
    sandbox_api_key = _sandbox_api_key_by_id(
        snapshot,
        sandbox_api_key_id,
    )
    _require_case_binding(
        case_id,
        sandbox_api_key.case_id,
    )
    case = _case_by_id(snapshot, sandbox_api_key.case_id)
    _require_revision(case, expected_revision)

    if (
        sandbox_api_key.status
        is ExternalConnectivitySandboxApiKeyStatus.REVOKED
    ):
        raise ExternalConnectivityQualificationError(
            "sandbox_api_key_already_revoked"
        )

    revoked_key = replace(
        sandbox_api_key,
        status=ExternalConnectivitySandboxApiKeyStatus.REVOKED,
        revoked_at=occurred_at,
        revoked_by=actor,
    )

    updated_case = advance_external_connectivity_case(
        case,
        target_state=ExternalConnectivityCaseState.SANDBOX_REVOKED,
        updated_at=occurred_at,
    )

    updated = _replace_sandbox_api_key(
        snapshot,
        revoked_key,
    )
    updated = _replace_case(updated, updated_case)
    save_external_connectivity_case_store(updated, path)

    return {
        "schema_version": (
            EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION
        ),
        "sandbox_api_key": _sandbox_api_key_projection(
            revoked_key
        ),
        "case": updated_case,
        "guardrails": _result_guardrails(),
    }


__all__ = [
    "EXTERNAL_CONNECTIVITY_QUALIFICATION_SCHEMA_VERSION",
    "ExternalConnectivityQualificationError",
    "issue_external_connectivity_qualification_key",
    "issue_external_connectivity_sandbox_api_key",
    "redeem_external_connectivity_qualification_key",
    "revoke_external_connectivity_qualification_key",
    "revoke_external_connectivity_sandbox_api_key",
    "suspend_external_connectivity_sandbox_api_key",
]
