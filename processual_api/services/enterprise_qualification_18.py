"""Stage 18 enterprise qualification and task-credential contracts.

This module is deliberately side-effect free. It defines the security model
used between validated enterprise cases, supervisor qualification decisions,
and task-scoped sandbox API credentials.

It does not issue credentials, call external services, enable production, or
approve runtime connectors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

QualificationStatus = Literal[
    "pending",
    "revision_required",
    "approved",
    "activated",
    "expired",
    "revoked",
    "rejected",
]

DecisionType = Literal[
    "request_revision",
    "approve_sandbox",
    "reject",
    "revoke",
]

TaskKind = Literal[
    "evidence",
    "reference",
    "configuration",
    "review",
    "sandbox_probe",
    "callback_probe",
    "contract_probe",
]

CredentialStatus = Literal[
    "not_eligible",
    "eligible",
    "active",
    "expired",
    "revoked",
    "rotation_required",
]


@dataclass(frozen=True, slots=True)
class TaskExecutionPolicy:
    track: str
    task_id: str
    task_kind: TaskKind
    executable: bool
    requires_qualification: bool
    credential_profile_id: str | None = None
    operational_profile_id: str | None = None
    connector_id: str | None = None
    allowed_scope_ids: tuple[str, ...] = ()
    environment: str = "sandbox"
    read_only: bool = True
    write_allowed: bool = False
    restricted_allowed: bool = False
    production_allowed: bool = False
    runtime_connector_approved: bool = False
    external_http_allowed: bool = False
    raw_secret_visible: bool = False
    maximum_ttl_days: int = 30
    maximum_usage: int = 100


@dataclass(frozen=True, slots=True)
class QualificationDecision:
    case_id: str
    client_id: str
    decision: DecisionType
    supervisor_id: str
    supervisor_session_key_id: str
    approved_task_ids: tuple[str, ...] = ()
    reason: str = ""
    decided_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    environment: str = "sandbox"
    production_allowed: bool = False
    runtime_connector_approved: bool = False
    raw_secret_visible: bool = False


@dataclass(frozen=True, slots=True)
class QualificationGrant:
    grant_id: str
    case_id: str
    client_id: str
    integration_track: str
    approved_task_ids: tuple[str, ...]
    approved_profile_ids: tuple[str, ...]
    issued_by_supervisor_id: str
    supervisor_session_key_id: str
    issued_at: str
    expires_at: str
    status: QualificationStatus = "approved"
    environment: str = "sandbox"
    revision: int = 1
    constraints: tuple[str, ...] = ()
    production_allowed: bool = False
    runtime_connector_approved: bool = False
    write_allowed: bool = False
    restricted_allowed: bool = False
    external_http_allowed: bool = False
    raw_secret_visible: bool = False


@dataclass(frozen=True, slots=True)
class TaskCredentialRecord:
    key_id: str
    case_id: str
    task_id: str
    client_id: str
    qualification_grant_id: str
    operational_profile_id: str
    issued_at: str
    expires_at: str
    status: CredentialStatus = "active"
    environment: str = "sandbox"
    usage_limit: int = 100
    usage_count: int = 0
    denied_count: int = 0
    last_used_at: str | None = None
    rotated_from_key_id: str | None = None
    revoked_at: str | None = None
    production_allowed: bool = False
    runtime_connector_approved: bool = False
    write_allowed: bool = False
    restricted_allowed: bool = False
    external_http_allowed: bool = False
    raw_secret_visible: bool = False


TASK_EXECUTION_POLICIES: dict[
    tuple[str, str],
    TaskExecutionPolicy,
] = {
    # Existing CAMARA intake tasks remain reference-only.
    ("camara", "capability_profile"): TaskExecutionPolicy(
        track="camara",
        task_id="capability_profile",
        task_kind="configuration",
        executable=False,
        requires_qualification=False,
    ),
    ("camara", "consent_reference"): TaskExecutionPolicy(
        track="camara",
        task_id="consent_reference",
        task_kind="reference",
        executable=False,
        requires_qualification=False,
    ),
    ("camara", "sandbox_endpoint"): TaskExecutionPolicy(
        track="camara",
        task_id="sandbox_endpoint",
        task_kind="reference",
        executable=False,
        requires_qualification=False,
    ),
    ("camara", "conformance_evidence"): TaskExecutionPolicy(
        track="camara",
        task_id="conformance_evidence",
        task_kind="evidence",
        executable=False,
        requires_qualification=False,
    ),

    # New controlled CAMARA execution task.
    ("camara", "sandbox_capability_probe"): TaskExecutionPolicy(
        track="camara",
        task_id="sandbox_capability_probe",
        task_kind="sandbox_probe",
        executable=True,
        requires_qualification=True,
        credential_profile_id="telecom_operations_api_reference",
        operational_profile_id=(
            "enterprise_telecom_conformance_read"
        ),
        connector_id="telecom_crm_reference",
        allowed_scope_ids=("crm:read",),
    ),

    # Existing TM Forum intake tasks.
    ("tmforum", "api_version"): TaskExecutionPolicy(
        track="tmforum",
        task_id="api_version",
        task_kind="configuration",
        executable=False,
        requires_qualification=False,
    ),
    ("tmforum", "contract_reference"): TaskExecutionPolicy(
        track="tmforum",
        task_id="contract_reference",
        task_kind="reference",
        executable=False,
        requires_qualification=False,
    ),
    ("tmforum", "ctk_evidence"): TaskExecutionPolicy(
        track="tmforum",
        task_id="ctk_evidence",
        task_kind="evidence",
        executable=False,
        requires_qualification=False,
    ),
    ("tmforum", "deviation_record"): TaskExecutionPolicy(
        track="tmforum",
        task_id="deviation_record",
        task_kind="review",
        executable=False,
        requires_qualification=False,
    ),

    # New controlled TM Forum execution task.
    ("tmforum", "ctk_contract_probe"): TaskExecutionPolicy(
        track="tmforum",
        task_id="ctk_contract_probe",
        task_kind="contract_probe",
        executable=True,
        requires_qualification=True,
        credential_profile_id="telecom_operations_api_reference",
        operational_profile_id=(
            "enterprise_telecom_conformance_read"
        ),
        connector_id="telecom_ticketing_reference",
        allowed_scope_ids=("ticket:read",),
    ),

    # Existing operator-specific intake tasks.
    ("operator", "dns_tls_reference"): TaskExecutionPolicy(
        track="operator",
        task_id="dns_tls_reference",
        task_kind="evidence",
        executable=False,
        requires_qualification=False,
    ),
    ("operator", "oauth_profile"): TaskExecutionPolicy(
        track="operator",
        task_id="oauth_profile",
        task_kind="configuration",
        executable=False,
        requires_qualification=False,
    ),
    ("operator", "callback_reference"): TaskExecutionPolicy(
        track="operator",
        task_id="callback_reference",
        task_kind="reference",
        executable=False,
        requires_qualification=False,
    ),
    ("operator", "sandbox_scope"): TaskExecutionPolicy(
        track="operator",
        task_id="sandbox_scope",
        task_kind="configuration",
        executable=False,
        requires_qualification=False,
    ),

    # Callback delivery remains blocked until a controlled
    # sandbox dispatcher is introduced and separately qualified.
    ("operator", "callback_delivery_probe"): TaskExecutionPolicy(
        track="operator",
        task_id="callback_delivery_probe",
        task_kind="callback_probe",
        executable=False,
        requires_qualification=True,
    ),
}


def get_task_execution_policy(
    track: str,
    task_id: str,
) -> TaskExecutionPolicy:
    """Return a task policy or a safe non-executable default."""

    policy = TASK_EXECUTION_POLICIES.get((track, task_id))

    if policy is not None:
        return policy

    return TaskExecutionPolicy(
        track=track,
        task_id=task_id,
        task_kind="reference",
        executable=False,
        requires_qualification=True,
    )


def executable_task_ids(track: str) -> tuple[str, ...]:
    return tuple(
        policy.task_id
        for policy in TASK_EXECUTION_POLICIES.values()
        if policy.track == track and policy.executable
    )


def task_credential_eligibility(
    *,
    case: dict[str, Any],
    task_id: str,
    grant: QualificationGrant | None,
) -> dict[str, Any]:
    """Evaluate eligibility without issuing or revealing a credential."""

    track = str(case.get("integration_track") or "")
    client_id = str(case.get("client_id") or "")
    case_id = str(case.get("case_id") or "")
    policy = get_task_execution_policy(track, task_id)

    blockers: list[str] = []

    if case.get("status") not in {
        "ready_for_review",
        "qualified",
        "qualification_activated",
    }:
        blockers.append("case_not_validated")

    if not policy.executable:
        blockers.append("task_not_executable")

    if not policy.requires_qualification:
        blockers.append("qualification_policy_missing")

    if grant is None:
        blockers.append("qualification_grant_missing")
    else:
        if grant.status not in {"approved", "activated"}:
            blockers.append("qualification_grant_inactive")

        if grant.case_id != case_id:
            blockers.append("grant_case_mismatch")

        if grant.client_id != client_id:
            blockers.append("grant_client_mismatch")

        if grant.integration_track != track:
            blockers.append("grant_track_mismatch")

        if task_id not in grant.approved_task_ids:
            blockers.append("task_not_approved")

        if grant.environment != "sandbox":
            blockers.append("environment_not_sandbox")

        if grant.production_allowed:
            blockers.append("production_permission_forbidden")

        if grant.runtime_connector_approved:
            blockers.append("runtime_connector_forbidden")

    eligible = not blockers

    return {
        "eligible": eligible,
        "credential_status": "eligible" if eligible else "not_eligible",
        "case_id": case_id,
        "client_id": client_id,
        "task_id": task_id,
        "integration_track": track,
        "credential_profile_id": policy.credential_profile_id,
        "operational_profile_id": policy.operational_profile_id,
        "connector_id": policy.connector_id,
        "allowed_scope_ids": list(policy.allowed_scope_ids),
        "blockers": blockers,
        "environment": "sandbox",
        "read_only": policy.read_only,
        "write_allowed": False,
        "restricted_allowed": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }


def safe_grant_projection(
    grant: QualificationGrant,
) -> dict[str, Any]:
    result = asdict(grant)

    # Internal authority linkage is never exposed to the client.
    result.pop("supervisor_session_key_id", None)

    result.update(
        {
            "production_allowed": False,
            "runtime_connector_approved": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "external_http_allowed": False,
            "raw_secret_visible": False,
        }
    )

    return result


def safe_task_credential_projection(
    credential: TaskCredentialRecord,
) -> dict[str, Any]:
    result = asdict(credential)

    result.update(
        {
            "production_allowed": False,
            "runtime_connector_approved": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "external_http_allowed": False,
            "raw_secret_visible": False,
        }
    )

    return result
