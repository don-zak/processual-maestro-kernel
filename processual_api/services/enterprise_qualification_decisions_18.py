"""Stage 18 supervisor qualification decision service."""

from __future__ import annotations

import secrets
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from processual_api.services.enterprise_qualification_18 import (
    QualificationDecision,
    QualificationGrant,
    executable_task_ids,
    get_task_execution_policy,
    safe_grant_projection,
)
from processual_api.services.enterprise_qualification_store_18 import (
    append_qualification_audit,
    load_qualification_store,
    save_qualification_store,
)


class QualificationDecisionError(ValueError):
    """Safe qualification decision rejection."""


def _now() -> datetime:
    return datetime.now(UTC)


def _case_identity(
    case: dict[str, Any],
) -> tuple[str, str, str]:
    case_id = str(case.get("case_id") or "").strip()
    client_id = str(case.get("client_id") or "").strip()
    track = str(
        case.get("integration_track") or ""
    ).strip()

    if not case_id:
        raise QualificationDecisionError(
            "case_id is required."
        )

    if not client_id:
        raise QualificationDecisionError(
            "client_id is required."
        )

    if track not in {
        "camara",
        "tmforum",
        "operator",
    }:
        raise QualificationDecisionError(
            "Unsupported integration track."
        )

    return case_id, client_id, track


def qualification_review_summary(
    case: dict[str, Any],
) -> dict[str, Any]:
    case_id, client_id, track = _case_identity(case)
    tasks = case.get("tasks", [])

    if not isinstance(tasks, list):
        tasks = []

    blockers: list[str] = []

    if case.get("status") != "ready_for_review":
        blockers.append(
            "case_not_ready_for_review"
        )

    if case.get("phase") != "supervisor_decision":
        blockers.append(
            "case_not_in_supervisor_decision_phase"
        )

    failed_tasks = [
        str(task.get("task_id") or "")
        for task in tasks
        if isinstance(task, dict)
        and task.get("validation") != "passed"
    ]

    if failed_tasks:
        blockers.append(
            "task_validation_incomplete"
        )

    executable = executable_task_ids(track)

    return {
        "case_id": case_id,
        "client_id": client_id,
        "integration_track": track,
        "case_status": str(
            case.get("status") or ""
        ),
        "phase": str(case.get("phase") or ""),
        "validated_task_count": sum(
            1
            for task in tasks
            if isinstance(task, dict)
            and task.get("validation") == "passed"
        ),
        "intake_task_count": len(tasks),
        "executable_task_ids": list(executable),
        "blockers": blockers,
        "reviewable": not blockers,
        "environment": "sandbox",
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


def _validate_approved_tasks(
    track: str,
    approved_task_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if not approved_task_ids:
        raise QualificationDecisionError(
            "At least one executable task must be selected."
        )

    normalized = tuple(
        dict.fromkeys(
            str(task_id).strip()
            for task_id in approved_task_ids
            if str(task_id).strip()
        )
    )

    allowed = set(executable_task_ids(track))

    rejected = [
        task_id
        for task_id in normalized
        if task_id not in allowed
    ]

    if rejected:
        raise QualificationDecisionError(
            "Only registered executable tasks "
            "may be approved."
        )

    for task_id in normalized:
        policy = get_task_execution_policy(
            track,
            task_id,
        )

        if (
            not policy.executable
            or not policy.requires_qualification
            or not policy.credential_profile_id
            or policy.environment != "sandbox"
            or policy.production_allowed
            or policy.runtime_connector_approved
            or policy.write_allowed
            or policy.restricted_allowed
            or policy.external_http_allowed
        ):
            raise QualificationDecisionError(
                "Executable task policy is unsafe."
            )

    return normalized


def approve_sandbox_qualification(
    *,
    case: dict[str, Any],
    supervisor_id: str,
    supervisor_session_key_id: str,
    approved_task_ids: tuple[str, ...],
    reason: str = "",
    ttl_days: int = 7,
    store_path: Path | None = None,
) -> dict[str, Any]:
    summary = qualification_review_summary(case)

    if not summary["reviewable"]:
        raise QualificationDecisionError(
            "Case is not ready for qualification."
        )

    if not supervisor_id.strip():
        raise QualificationDecisionError(
            "supervisor_id is required."
        )

    if not supervisor_session_key_id.strip():
        raise QualificationDecisionError(
            "Validated supervisor session is required."
        )

    if ttl_days < 1 or ttl_days > 30:
        raise QualificationDecisionError(
            "Qualification TTL must be between 1 and 30 days."
        )

    case_id = summary["case_id"]
    client_id = summary["client_id"]
    track = summary["integration_track"]

    selected_tasks = _validate_approved_tasks(
        track,
        approved_task_ids,
    )

    now = _now()
    store = load_qualification_store(store_path)

    active = next(
        (
            item
            for item in store["grants"]
            if isinstance(item, dict)
            and item.get("case_id") == case_id
            and item.get("client_id") == client_id
            and item.get("status")
            in {"approved", "activated"}
        ),
        None,
    )

    if active is not None:
        raise QualificationDecisionError(
            "An active qualification grant already exists."
        )

    profile_ids = tuple(
        get_task_execution_policy(
            track,
            task_id,
        ).credential_profile_id
        or ""
        for task_id in selected_tasks
    )

    decision = QualificationDecision(
        case_id=case_id,
        client_id=client_id,
        decision="approve_sandbox",
        supervisor_id=supervisor_id.strip(),
        supervisor_session_key_id=(
            supervisor_session_key_id.strip()
        ),
        approved_task_ids=selected_tasks,
        reason=reason.strip(),
        decided_at=now.isoformat(),
    )

    grant = QualificationGrant(
        grant_id=(
            f"qgrant_{secrets.token_hex(8)}"
        ),
        case_id=case_id,
        client_id=client_id,
        integration_track=track,
        approved_task_ids=selected_tasks,
        approved_profile_ids=profile_ids,
        issued_by_supervisor_id=(
            supervisor_id.strip()
        ),
        supervisor_session_key_id=(
            supervisor_session_key_id.strip()
        ),
        issued_at=now.isoformat(),
        expires_at=(
            now + timedelta(days=ttl_days)
        ).isoformat(),
        status="approved",
        constraints=(
            "sandbox_only",
            "read_only",
            "no_external_http",
            "no_runtime_connector",
            "no_production",
        ),
    )

    decision_record = asdict(decision)
    grant_record = asdict(grant)

    store["decisions"].append(
        decision_record
    )
    store["grants"].append(
        grant_record
    )

    append_qualification_audit(
        store,
        event="qualification_approved",
        case_id=case_id,
        client_id=client_id,
        supervisor_id=supervisor_id.strip(),
        supervisor_session_key_id=(
            supervisor_session_key_id.strip()
        ),
        grant_id=grant.grant_id,
        task_ids=selected_tasks,
        occurred_at=now.isoformat(),
        reason=reason.strip(),
    )

    save_qualification_store(
        store,
        store_path,
    )

    return {
        "status": "approved",
        "decision": {
            "case_id": decision.case_id,
            "client_id": decision.client_id,
            "decision": decision.decision,
            "supervisor_id": decision.supervisor_id,
            "approved_task_ids": list(
                decision.approved_task_ids
            ),
            "reason": decision.reason,
            "decided_at": decision.decided_at,
            "environment": "sandbox",
            "production_allowed": False,
            "runtime_connector_approved": False,
            "raw_secret_visible": False,
        },
        "grant": safe_grant_projection(grant),
    }


def request_qualification_revision(
    *,
    case: dict[str, Any],
    supervisor_id: str,
    supervisor_session_key_id: str,
    reason: str,
    store_path: Path | None = None,
) -> dict[str, Any]:
    case_id, client_id, _track = _case_identity(
        case
    )

    if not supervisor_id.strip():
        raise QualificationDecisionError(
            "supervisor_id is required."
        )

    if not supervisor_session_key_id.strip():
        raise QualificationDecisionError(
            "Validated supervisor session is required."
        )

    if not reason.strip():
        raise QualificationDecisionError(
            "Revision reason is required."
        )

    now = _now()

    decision = QualificationDecision(
        case_id=case_id,
        client_id=client_id,
        decision="request_revision",
        supervisor_id=supervisor_id.strip(),
        supervisor_session_key_id=(
            supervisor_session_key_id.strip()
        ),
        reason=reason.strip(),
        decided_at=now.isoformat(),
    )

    store = load_qualification_store(store_path)
    store["decisions"].append(
        asdict(decision)
    )

    append_qualification_audit(
        store,
        event="qualification_revision_requested",
        case_id=case_id,
        client_id=client_id,
        supervisor_id=supervisor_id.strip(),
        supervisor_session_key_id=(
            supervisor_session_key_id.strip()
        ),
        occurred_at=now.isoformat(),
        reason=reason.strip(),
    )

    save_qualification_store(
        store,
        store_path,
    )

    return {
        "status": "revision_required",
        "case_id": case_id,
        "client_id": client_id,
        "reason": reason.strip(),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


def list_safe_qualification_grants(
    *,
    client_id: str | None = None,
    case_id: str | None = None,
    store_path: Path | None = None,
) -> list[dict[str, Any]]:
    store = load_qualification_store(store_path)
    results: list[dict[str, Any]] = []

    for item in store["grants"]:
        if not isinstance(item, dict):
            continue

        if (
            client_id is not None
            and item.get("client_id") != client_id
        ):
            continue

        if (
            case_id is not None
            and item.get("case_id") != case_id
        ):
            continue

        safe = dict(item)
        safe.pop(
            "supervisor_session_key_id",
            None,
        )

        safe.update(
            {
                "production_allowed": False,
                "runtime_connector_approved": False,
                "write_allowed": False,
                "restricted_allowed": False,
                "external_http_allowed": False,
                "raw_secret_visible": False,
            }
        )

        results.append(safe)

    return results

def activate_enterprise_qualification(
    *,
    case: dict[str, Any],
    client_id: str,
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Activate one approved sandbox qualification grant.

    Activation changes qualification metadata only. It does not issue,
    redeem, rotate, or expose any credential and does not enable runtime,
    external HTTP, write, restricted, or production execution.
    """
    case_id, case_client_id, _track = _case_identity(case)
    normalized_client_id = str(client_id or "").strip()

    if not normalized_client_id:
        raise QualificationDecisionError(
            "client_id is required."
        )

    if normalized_client_id != case_client_id:
        raise QualificationDecisionError(
            "Qualification grant does not belong to this client."
        )

    store = load_qualification_store(store_path)
    matching = [
        item
        for item in store["grants"]
        if isinstance(item, dict)
        and item.get("case_id") == case_id
        and item.get("client_id") == normalized_client_id
        and item.get("status") in {"approved", "activated"}
    ]

    if not matching:
        raise QualificationDecisionError(
            "Approved qualification grant not found."
        )

    if len(matching) > 1:
        raise QualificationDecisionError(
            "Multiple active qualification grants were found."
        )

    grant = matching[0]
    now = _now()

    expires_at_raw = str(
        grant.get("expires_at") or ""
    ).strip()

    try:
        expires_at = datetime.fromisoformat(
            expires_at_raw.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise QualificationDecisionError(
            "Qualification grant expiry is invalid."
        ) from exc

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= now:
        grant["status"] = "expired"
        save_qualification_store(
            store,
            store_path,
        )
        raise QualificationDecisionError(
            "Qualification grant has expired."
        )

    unsafe = (
        str(grant.get("environment") or "") != "sandbox"
        or grant.get("production_allowed") is not False
        or grant.get("runtime_connector_approved") is not False
        or grant.get("write_allowed") is not False
        or grant.get("restricted_allowed") is not False
        or grant.get("external_http_allowed") is not False
        or grant.get("raw_secret_visible") is not False
    )

    if unsafe:
        raise QualificationDecisionError(
            "Qualification grant violates sandbox safety boundaries."
        )

    approved_task_ids = tuple(
        str(task_id or "").strip()
        for task_id in grant.get("approved_task_ids", [])
        if str(task_id or "").strip()
    )

    if not approved_task_ids:
        raise QualificationDecisionError(
            "Qualification grant has no approved tasks."
        )

    already_activated = (
        grant.get("status") == "activated"
    )

    if not already_activated:
        grant["status"] = "activated"
        grant["activated_at"] = now.isoformat()

        audit_entry = {
            "event": "qualification_activated",
            "case_id": case_id,
            "client_id": normalized_client_id,
            "actor_type": "client",
            "actor_id": normalized_client_id,
            "grant_id": str(
                grant.get("grant_id") or ""
            ),
            "task_ids": list(approved_task_ids),
            "occurred_at": now.isoformat(),
            "reason": "",
            "production_allowed": False,
            "runtime_connector_approved": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "external_http_allowed": False,
            "raw_secret_visible": False,
        }

        store.setdefault("audit", []).append(
            audit_entry
        )

        save_qualification_store(
            store,
            store_path,
        )

    safe_grant = dict(grant)
    safe_grant.pop(
        "supervisor_session_key_id",
        None,
    )

    safe_grant.update(
        {
            "production_allowed": False,
            "runtime_connector_approved": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "external_http_allowed": False,
            "raw_secret_visible": False,
        }
    )

    return {
        "status": "activated",
        "case_id": case_id,
        "client_id": normalized_client_id,
        "case_phase": "qualification_activated",
        "already_activated": already_activated,
        "grant": safe_grant,
        "credential_issued": False,
        "binding_created": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }
