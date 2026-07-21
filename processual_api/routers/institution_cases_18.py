"""Client-safe operational workflow for institution integration cases."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

from processual_api.auth.security import get_current_user

from . import settings as settings_module

TRACK_TASKS: dict[str, tuple[dict[str, str], ...]] = {
    "camara": (
        {"task_id": "capability_profile", "label": "Select capability profile", "input_kind": "reference"},
        {
            "task_id": "consent_reference",
            "label": "Register consent and authorization reference",
            "input_kind": "reference",
        },
        {"task_id": "sandbox_endpoint", "label": "Register sandbox endpoint", "input_kind": "url"},
        {
            "task_id": "conformance_evidence",
            "label": "Attach conformance evidence reference",
            "input_kind": "reference",
        },
    ),
    "tmforum": (
        {"task_id": "api_version", "label": "Select TM Forum Open API and version", "input_kind": "reference"},
        {"task_id": "contract_reference", "label": "Register contract or schema reference", "input_kind": "reference"},
        {"task_id": "ctk_evidence", "label": "Attach CTK evidence reference", "input_kind": "reference"},
        {"task_id": "deviation_record", "label": "Record operator-specific deviations", "input_kind": "reference"},
    ),
    "operator": (
        {"task_id": "dns_tls_reference", "label": "Register DNS and TLS reference package", "input_kind": "reference"},
        {"task_id": "oauth_profile", "label": "Register OAuth or OIDC profile", "input_kind": "reference"},
        {"task_id": "callback_reference", "label": "Register callback and allowlist references", "input_kind": "url"},
        {
            "task_id": "sandbox_scope",
            "label": "Define sandbox scope and escalation contacts",
            "input_kind": "reference",
        },
    ),
}

CASE_TYPES = {
    "camara": "camara_integration_case",
    "tmforum": "tmforum_integration_case",
    "operator": "operator_integration_case",
}

FORBIDDEN_REFERENCE_MARKERS = (
    "client_secret=",
    "access_token=",
    "authorization: bearer ",
    "private_key=",
    "password=",
    "api_key=",
    "sk-",
)


class InstitutionCaseCreate(BaseModel):
    integration_track: Literal["camara", "tmforum", "operator"]
    title: str | None = Field(default=None, max_length=160)


class InstitutionTaskUpdate(BaseModel):
    status: Literal["not_started", "in_progress", "completed", "blocked"]
    reference: str = Field(default="", max_length=500)
    note: str = Field(default="", max_length=500)


def _identity(current_user: dict) -> tuple[str, str]:
    user_id = str(current_user.get("user_id") or current_user.get("sub") or "default")
    client_id = str(current_user.get("client_id") or user_id)
    return user_id, client_id


def _case_store(raw: dict[str, Any]) -> list[dict[str, Any]]:
    value = raw.get("institution_integration_cases", [])
    return value if isinstance(value, list) else []


def _safe_reference(value: str) -> str:
    reference = str(value or "").strip()
    lowered = reference.lower()
    if any(marker in lowered for marker in FORBIDDEN_REFERENCE_MARKERS):
        raise HTTPException(status_code=422, detail="Raw secrets are not allowed in institution references.")
    return reference


def _task_template(track: str) -> list[dict[str, Any]]:
    return [
        {
            **task,
            "status": "not_started",
            "reference": "",
            "note": "",
            "updated_at": None,
            "validation": "not_checked",
        }
        for task in TRACK_TASKS[track]
    ]


def _progress(case: dict[str, Any]) -> int:
    tasks = case.get("tasks", [])
    if not tasks:
        return 0
    completed = sum(1 for task in tasks if task.get("status") == "completed")
    return round(completed * 100 / len(tasks))


def _safe_case(case: dict[str, Any]) -> dict[str, Any]:
    result = {
        "case_id": case.get("case_id"),
        "case_type": case.get("case_type"),
        "integration_track": case.get("integration_track"),
        "title": case.get("title"),
        "status": case.get("status", "draft"),
        "phase": case.get("phase", "technical_intake"),
        "tasks": case.get("tasks", []),
        "progress_percent": _progress(case),
        "created_at": case.get("created_at"),
        "updated_at": case.get("updated_at"),
        "sandbox_requested": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }
    return result


def _find_case(cases: list[dict[str, Any]], case_id: str, client_id: str) -> dict[str, Any]:
    case = next(
        (
            item
            for item in cases
            if isinstance(item, dict)
            and item.get("case_id") == case_id
            and str(item.get("client_id") or "") == client_id
        ),
        None,
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Institution integration case not found.")
    return case


@settings_module.router.get("/client/integration-cases", response_model=dict)
async def list_institution_cases(current_user: dict = Depends(get_current_user)):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    cases = [
        _safe_case(case)
        for case in _case_store(raw)
        if isinstance(case, dict) and str(case.get("client_id") or "") == client_id
    ]
    cases.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {
        "status": "ready",
        "case_count": len(cases),
        "cases": cases,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


@settings_module.router.post("/client/integration-cases", response_model=dict, status_code=201)
async def create_institution_case(
    body: InstitutionCaseCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    cases = _case_store(raw)
    active = next(
        (
            case
            for case in cases
            if isinstance(case, dict)
            and case.get("client_id") == client_id
            and case.get("integration_track") == body.integration_track
            and case.get("status") in {"draft", "in_progress", "ready_for_review"}
        ),
        None,
    )
    if active is not None:
        return {"status": "existing", "case": _safe_case(active)}

    now = datetime.now(UTC).isoformat()
    case = {
        "case_id": f"icase_{secrets.token_hex(8)}",
        "case_type": CASE_TYPES[body.integration_track],
        "integration_track": body.integration_track,
        "title": body.title or CASE_TYPES[body.integration_track].replace("_", " ").title(),
        "client_id": client_id,
        "user_id": user_id,
        "status": "draft",
        "phase": "technical_intake",
        "tasks": _task_template(body.integration_track),
        "created_at": now,
        "updated_at": now,
        "sandbox_requested": True,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }
    cases.append(case)
    raw["institution_integration_cases"] = cases
    settings_module._save_raw(user_id, raw)
    return {"status": "created", "case": _safe_case(case)}


@settings_module.router.patch("/client/integration-cases/{case_id}/tasks/{task_id}", response_model=dict)
async def update_institution_case_task(
    case_id: str,
    task_id: str,
    body: InstitutionTaskUpdate,
    current_user: dict = Depends(get_current_user),
):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    cases = _case_store(raw)
    case = _find_case(cases, case_id, client_id)
    task = next((item for item in case.get("tasks", []) if item.get("task_id") == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="Integration task not found.")

    reference = _safe_reference(body.reference)
    if body.status == "completed" and not reference:
        raise HTTPException(status_code=422, detail="A client-safe reference is required before completing this task.")

    now = datetime.now(UTC).isoformat()
    task.update(
        {
            "status": body.status,
            "reference": reference,
            "note": _safe_reference(body.note),
            "updated_at": now,
            "validation": "pending" if reference else "not_checked",
        }
    )
    case["status"] = "in_progress"
    case["updated_at"] = now
    if _progress(case) == 100:
        case["status"] = "ready_for_validation"
        case["phase"] = "automated_validation"
    raw["institution_integration_cases"] = cases
    settings_module._save_raw(user_id, raw)
    return {"status": "updated", "case": _safe_case(case)}


@settings_module.router.post("/client/integration-cases/{case_id}/validate", response_model=dict)
async def validate_institution_case(
    case_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id, client_id = _identity(current_user)
    raw = settings_module._load_raw(user_id)
    cases = _case_store(raw)
    case = _find_case(cases, case_id, client_id)
    blockers: list[str] = []

    for task in case.get("tasks", []):
        reference = str(task.get("reference") or "").strip()
        if task.get("status") != "completed":
            blockers.append(f"{task.get('task_id')}: task is not completed")
            task["validation"] = "blocked"
            continue
        if not reference:
            blockers.append(f"{task.get('task_id')}: reference is missing")
            task["validation"] = "blocked"
            continue
        if task.get("input_kind") == "url" and not re.match(r"^https?://[^\s]+$", reference):
            blockers.append(f"{task.get('task_id')}: valid HTTP(S) reference required")
            task["validation"] = "blocked"
            continue
        task["validation"] = "passed"

    now = datetime.now(UTC).isoformat()
    case["updated_at"] = now
    if blockers:
        case["status"] = "validation_blocked"
        case["phase"] = "technical_intake"
    else:
        case["status"] = "ready_for_review"
        case["phase"] = "supervisor_decision"
    raw["institution_integration_cases"] = cases
    settings_module._save_raw(user_id, raw)
    return {
        "status": "passed" if not blockers else "blocked",
        "blockers": blockers,
        "case": _safe_case(case),
        "supervisor_required": not blockers,
        "production_allowed": False,
        "runtime_connector_approved": False,
    }
