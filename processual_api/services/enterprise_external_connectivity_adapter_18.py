"""Stage 18 enterprise-to-R10 qualification binding adapter.

This service builds and validates a safe binding plan between:

- a validated institution integration case;
- an approved Stage 18 qualification grant;
- one explicitly executable enterprise task;
- one existing R10 external-connectivity case;
- connector-supported sandbox scopes.

It does not issue, redeem, rotate, suspend, or revoke any key.
It never receives or returns raw credential material.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

from processual_api.integrations.api_key_operational_profiles import (
    get_api_key_operational_profile,
)
from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
)
from processual_api.services.enterprise_qualification_18 import (
    QualificationGrant,
    get_task_execution_policy,
    task_credential_eligibility,
)


class EnterpriseR10BindingError(ValueError):
    """Safe rejection for an invalid enterprise-to-R10 binding."""


@dataclass(frozen=True, slots=True)
class EnterpriseR10BindingPlan:
    institution_case_id: str
    institution_task_id: str
    qualification_grant_id: str
    client_id: str
    integration_track: str

    external_connectivity_case_id: str
    connector_id: str
    operational_profile_id: str
    target_environment: str

    requested_scope_ids: tuple[str, ...]
    connector_scope_ids: tuple[str, ...]

    qualification_key_required: bool = True
    qualification_redemption_required: bool = True
    sandbox_api_key_required: bool = True

    production_allowed: bool = False
    runtime_connector_approved: bool = False
    external_http_allowed: bool = False
    write_allowed: bool = False
    restricted_allowed: bool = False
    raw_secret_visible: bool = False


def _identifier(field_name: str, value: Any) -> str:
    normalized = str(value or "").strip()

    if not normalized:
        raise EnterpriseR10BindingError(
            f"{field_name}_required"
        )

    return normalized


def _normalized_scope_ids(
    values: Iterable[str],
    *,
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, str):
        raise EnterpriseR10BindingError(
            f"{field_name}_invalid"
        )

    normalized = tuple(
        str(value or "").strip().lower()
        for value in values
        if str(value or "").strip()
    )

    if not normalized:
        raise EnterpriseR10BindingError(
            f"{field_name}_required"
        )

    if len(set(normalized)) != len(normalized):
        raise EnterpriseR10BindingError(
            f"{field_name}_duplicate"
        )

    return normalized


def _r10_case_value(
    external_case: Any,
    field_name: str,
) -> Any:
    if isinstance(external_case, dict):
        return external_case.get(field_name)

    return getattr(
        external_case,
        field_name,
        None,
    )


def _allowed_r10_states() -> set[str]:
    return {
        "readiness_approved",
        "qualification_key_issued",
        "qualification_redeemed",
    }


def build_enterprise_r10_binding_plan(
    *,
    institution_case: dict[str, Any],
    institution_task_id: str,
    grant: QualificationGrant,
    external_connectivity_case: Any,
    requested_scope_ids: Iterable[str],
    connector_scope_ids: Iterable[str],
) -> dict[str, Any]:
    """Validate the binding and return a secret-free orchestration plan."""

    institution_task_id = _identifier(
        "institution_task_id",
        institution_task_id,
    )

    eligibility = task_credential_eligibility(
        case=institution_case,
        task_id=institution_task_id,
        grant=grant,
    )

    if not eligibility["eligible"]:
        blockers = ",".join(
            str(blocker)
            for blocker in eligibility["blockers"]
        )

        raise EnterpriseR10BindingError(
            f"task_credential_not_eligible:{blockers}"
        )

    institution_case_id = _identifier(
        "institution_case_id",
        institution_case.get("case_id"),
    )
    client_id = _identifier(
        "client_id",
        institution_case.get("client_id"),
    )
    integration_track = _identifier(
        "integration_track",
        institution_case.get(
            "integration_track"
        ),
    )

    external_case_id = _identifier(
        "external_connectivity_case_id",
        _r10_case_value(
            external_connectivity_case,
            "case_id",
        ),
    )
    external_client_id = _identifier(
        "external_client_id",
        _r10_case_value(
            external_connectivity_case,
            "client_id",
        ),
    )
    connector_id = _identifier(
        "connector_id",
        _r10_case_value(
            external_connectivity_case,
            "connector_id",
        ),
    )
    credential_profile_id = _identifier(
        "credential_profile_id",
        _r10_case_value(
            external_connectivity_case,
            "credential_profile_id",
        ),
    )
    target_environment = _identifier(
        "target_environment",
        _r10_case_value(
            external_connectivity_case,
            "target_environment",
        ),
    ).lower()

    raw_state = _r10_case_value(
        external_connectivity_case,
        "state",
    )

    external_state = str(
        getattr(raw_state, "value", raw_state) or ""
    ).strip().lower()

    if external_client_id != client_id:
        raise EnterpriseR10BindingError(
            "external_case_client_mismatch"
        )

    if target_environment != "sandbox":
        raise EnterpriseR10BindingError(
            "external_case_environment_not_sandbox"
        )

    if external_state not in _allowed_r10_states():
        raise EnterpriseR10BindingError(
            "external_case_not_ready_for_qualification"
        )

    policy = get_task_execution_policy(
        integration_track,
        institution_task_id,
    )

    policy_connector_id = _identifier(
        "policy_connector_id",
        policy.connector_id,
    )
    operational_profile_id = _identifier(
        "operational_profile_id",
        policy.operational_profile_id,
    )
    policy_scope_ids = _normalized_scope_ids(
        policy.allowed_scope_ids,
        field_name="policy_allowed_scope_ids",
    )

    if connector_id != policy_connector_id:
        raise EnterpriseR10BindingError(
            "connector_policy_mismatch"
        )

    try:
        operational_profile = (
            get_api_key_operational_profile(
                operational_profile_id
            )
        )
    except KeyError as exc:
        raise EnterpriseR10BindingError(
            "operational_profile_unknown"
        ) from exc

    if operational_profile.get("environment") != "sandbox":
        raise EnterpriseR10BindingError(
            "operational_profile_not_sandbox"
        )

    if operational_profile.get("read_only") is not True:
        raise EnterpriseR10BindingError(
            "operational_profile_not_read_only"
        )

    if operational_profile.get("write_allowed") is not False:
        raise EnterpriseR10BindingError(
            "operational_profile_write_forbidden"
        )

    if (
        operational_profile.get("restricted_allowed")
        is not False
    ):
        raise EnterpriseR10BindingError(
            "operational_profile_restricted_forbidden"
        )

    if (
        operational_profile.get("production_allowed")
        is not False
    ):
        raise EnterpriseR10BindingError(
            "operational_profile_production_forbidden"
        )

    if (
        operational_profile.get(
            "runtime_connector_approved"
        )
        is not False
    ):
        raise EnterpriseR10BindingError(
            "operational_profile_runtime_forbidden"
        )

    operational_scope_ids = _normalized_scope_ids(
        operational_profile.get("allowed_scopes") or (),
        field_name="operational_profile_scope_ids",
    )

    if not set(policy_scope_ids).issubset(
        set(operational_scope_ids)
    ):
        raise EnterpriseR10BindingError(
            "policy_scope_not_allowed_by_operational_profile"
        )

    try:
        registered_connector = (
            get_runtime_connector_contract(
                connector_id
            )
        )
    except KeyError as exc:
        raise EnterpriseR10BindingError(
            "connector_not_registered"
        ) from exc

    registered_read_scope_ids = tuple(
        capability.scope_id
        for capability in registered_connector.capabilities
        if capability.access_mode == "read"
    )

    if not set(policy_scope_ids).issubset(
        set(registered_read_scope_ids)
    ):
        raise EnterpriseR10BindingError(
            "policy_scope_not_supported_by_registered_connector"
        )

    if (
        policy.credential_profile_id
        != credential_profile_id
    ):
        raise EnterpriseR10BindingError(
            "credential_profile_mismatch"
        )

    if (
        credential_profile_id
        not in grant.approved_profile_ids
    ):
        raise EnterpriseR10BindingError(
            "credential_profile_not_approved"
        )

    requested = _normalized_scope_ids(
        requested_scope_ids,
        field_name="requested_scope_ids",
    )
    connector_scopes = _normalized_scope_ids(
        connector_scope_ids,
        field_name="connector_scope_ids",
    )

    forbidden_fragments = (
        "production",
        "admin:",
        "write",
        "delete",
        "execute",
        "secret",
        "credential",
        "runtime",
    )

    unsafe_scope_ids = tuple(
        scope_id
        for scope_id in requested
        if any(
            fragment in scope_id
            for fragment in forbidden_fragments
        )
    )

    if unsafe_scope_ids:
        raise EnterpriseR10BindingError(
            "requested_scope_not_stage18_safe"
        )

    if not set(requested).issubset(
        set(policy_scope_ids)
    ):
        raise EnterpriseR10BindingError(
            "requested_scope_not_allowed_by_task_policy"
        )

    if not set(requested).issubset(
        set(operational_scope_ids)
    ):
        raise EnterpriseR10BindingError(
            "requested_scope_not_allowed_by_operational_profile"
        )

    if not set(connector_scopes).issubset(
        set(registered_read_scope_ids)
    ):
        raise EnterpriseR10BindingError(
            "connector_scope_not_declared_as_registered_read"
        )

    if not set(requested).issubset(
        set(connector_scopes)
    ):
        raise EnterpriseR10BindingError(
            "requested_scope_not_supported_by_connector"
        )

    plan = EnterpriseR10BindingPlan(
        institution_case_id=(
            institution_case_id
        ),
        institution_task_id=(
            institution_task_id
        ),
        qualification_grant_id=(
            grant.grant_id
        ),
        client_id=client_id,
        integration_track=(
            integration_track
        ),
        external_connectivity_case_id=(
            external_case_id
        ),
        connector_id=connector_id,
        operational_profile_id=(
            operational_profile_id
        ),
        target_environment="sandbox",
        requested_scope_ids=requested,
        connector_scope_ids=(
            connector_scopes
        ),
    )

    result = asdict(plan)

    result.update(
        {
            "binding_status": "validated",
            "next_required_state": (
                "qualification_key"
                if external_state
                == "readiness_approved"
                else (
                    "qualification_redemption"
                    if external_state
                    == "qualification_key_issued"
                    else "sandbox_api_key"
                )
            ),
            "external_case_state": (
                external_state
            ),
            "production_allowed": False,
            "runtime_connector_approved": False,
            "external_http_allowed": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "raw_secret_visible": False,
        }
    )

    return result
