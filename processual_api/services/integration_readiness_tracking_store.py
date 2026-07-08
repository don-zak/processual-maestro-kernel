from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from processual_api.integrations.readiness_tracking import (
    IntegrationReadinessCase,
    ReadinessItemStatus,
    ReadinessTimelineEvent,
    SafeEvidenceReference,
    readiness_case_from_check,
    readiness_case_summary,
    update_readiness_case_item,
)

DEFAULT_TRACKING_STORE_PATH = Path("data/integration_readiness_cases.json")


def tracking_store_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else DEFAULT_TRACKING_STORE_PATH


def _ensure_store_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_reference_from_dict(value: dict[str, Any] | None) -> SafeEvidenceReference | None:
    if not value:
        return None
    return SafeEvidenceReference(
        reference_type=str(value.get("reference_type", "")),
        reference_label=str(value.get("reference_label", "")),
    )


def _item_from_dict(value: dict[str, Any]) -> ReadinessItemStatus:
    return ReadinessItemStatus(
        key=str(value.get("key", "")),
        status=str(value.get("status", "missing")),
        safe_reference=_safe_reference_from_dict(value.get("safe_reference")),
        verified_by=value.get("verified_by"),
        verified_at=value.get("verified_at"),
        note=str(value.get("note", "")),
    )


def _timeline_event_from_dict(value: dict[str, Any]) -> ReadinessTimelineEvent:
    return ReadinessTimelineEvent(
        event_type=str(value.get("event_type", "")),
        actor=str(value.get("actor", "")),
        safe_summary=str(value.get("safe_summary", "")),
        created_at=str(value.get("created_at", "")),
    )


def readiness_case_from_dict(value: dict[str, Any]) -> IntegrationReadinessCase:
    return IntegrationReadinessCase(
        case_id=str(value.get("case_id", "")),
        client_id=str(value.get("client_id", "")),
        request_id=str(value.get("request_id", "")),
        adapter_contract_id=str(value.get("adapter_contract_id", "")),
        credential_profile_id=str(value.get("credential_profile_id", "")),
        operational_profile_id=str(value.get("operational_profile_id", "")),
        status=str(value.get("status", "blocked")),
        input_statuses=tuple(
            _item_from_dict(item) for item in value.get("input_statuses", [])
        ),
        security_control_statuses=tuple(
            _item_from_dict(item)
            for item in value.get("security_control_statuses", [])
        ),
        timeline=tuple(
            _timeline_event_from_dict(event) for event in value.get("timeline", [])
        ),
        assigned_supervisor=str(value.get("assigned_supervisor", "")),
        sandbox_ready=bool(value.get("sandbox_ready", False)),
        production_allowed=bool(value.get("production_allowed", False)),
        runtime_connector_approved=bool(
            value.get("runtime_connector_approved", False)
        ),
        external_http_enabled=bool(value.get("external_http_enabled", False)),
        raw_secret_visible=bool(value.get("raw_secret_visible", False)),
        created_at=str(value.get("created_at", "")),
        updated_at=str(value.get("updated_at", "")),
    )


def readiness_case_to_dict(case: IntegrationReadinessCase) -> dict[str, Any]:
    payload = asdict(case)
    payload["production_allowed"] = False
    payload["runtime_connector_approved"] = False
    payload["external_http_enabled"] = False
    payload["raw_secret_visible"] = False
    return payload


def load_readiness_cases(
    path: str | Path | None = None,
) -> tuple[IntegrationReadinessCase, ...]:
    store_path = tracking_store_path(path)
    if not store_path.exists():
        return ()

    raw_text = store_path.read_text(encoding="utf-8")
    if not raw_text.strip():
        return ()

    payload = json.loads(raw_text)
    if isinstance(payload, dict):
        records = payload.get("cases", [])
    else:
        records = payload

    return tuple(readiness_case_from_dict(record) for record in records)


def save_readiness_cases(
    cases: tuple[IntegrationReadinessCase, ...],
    path: str | Path | None = None,
) -> None:
    store_path = tracking_store_path(path)
    _ensure_store_parent(store_path)
    payload = {
        "schema_version": "integration_readiness_tracking_11p",
        "cases": [readiness_case_to_dict(case) for case in cases],
    }
    store_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _replace_case(
    cases: tuple[IntegrationReadinessCase, ...],
    new_case: IntegrationReadinessCase,
) -> tuple[IntegrationReadinessCase, ...]:
    replaced = False
    updated: list[IntegrationReadinessCase] = []
    for case in cases:
        if case.case_id == new_case.case_id:
            updated.append(new_case)
            replaced = True
        else:
            updated.append(case)
    if not replaced:
        updated.append(new_case)
    return tuple(updated)


def create_tracking_case_from_payload(
    payload: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, Any]:
    readiness_check = payload.get("readiness_check") or {}
    if not readiness_check:
        readiness_check = {
            "readiness_check_id": payload.get("readiness_check_id", ""),
            "adapter_contract_id": payload.get("adapter_contract_id", ""),
            "credential_profile_id": payload.get("credential_profile_id", ""),
            "missing_inputs": payload.get("missing_inputs", []),
            "missing_security_controls": payload.get(
                "missing_security_controls", []
            ),
        }

    case = readiness_case_from_check(
        readiness_check,
        client_id=str(payload.get("client_id", "")),
        request_id=str(payload.get("request_id", "")),
        operational_profile_id=str(payload.get("operational_profile_id", "")),
        assigned_supervisor=str(payload.get("assigned_supervisor", "")),
    )

    cases = _replace_case(load_readiness_cases(path), case)
    save_readiness_cases(cases, path)
    return readiness_case_summary(case)


def update_tracking_case_item_from_payload(
    case_id: str,
    payload: dict[str, Any],
    path: str | Path | None = None,
) -> dict[str, Any]:
    cases = load_readiness_cases(path)
    target = next((case for case in cases if case.case_id == case_id), None)
    if target is None:
        raise KeyError(f"readiness tracking case not found: {case_id}")

    reference_payload = payload.get("safe_reference") or None
    safe_reference = _safe_reference_from_dict(reference_payload)

    updated_case = update_readiness_case_item(
        target,
        item_kind=str(payload.get("item_kind", "")),
        item_key=str(payload.get("item_key", "")),
        status=str(payload.get("status", "")),
        actor=str(payload.get("actor", "")),
        safe_reference=safe_reference,
        note=str(payload.get("note", "")),
    )

    save_readiness_cases(_replace_case(cases, updated_case), path)
    return readiness_case_summary(updated_case)


def admin_tracking_summary_payload(
    path: str | Path | None = None,
) -> dict[str, Any]:
    cases = load_readiness_cases(path)
    summaries = [readiness_case_summary(case) for case in cases]

    provided_inputs = 0
    verified_items = 0
    rejected_items = 0
    timeline_events = 0

    for case in cases:
        for item in case.input_statuses + case.security_control_statuses:
            if item.status == "provided":
                provided_inputs += 1
            if item.status == "verified":
                verified_items += 1
            if item.status == "rejected":
                rejected_items += 1
        timeline_events += len(case.timeline)

    return {
        "tracking_foundation": "available",
        "schema_version": "integration_readiness_tracking_11p",
        "persisted_cases": len(cases),
        "provided_inputs": provided_inputs,
        "verified_items": verified_items,
        "rejected_items": rejected_items,
        "timeline_events": timeline_events,
        "cases": summaries,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_enabled": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "DEFAULT_TRACKING_STORE_PATH",
    "admin_tracking_summary_payload",
    "create_tracking_case_from_payload",
    "load_readiness_cases",
    "readiness_case_from_dict",
    "readiness_case_to_dict",
    "save_readiness_cases",
    "tracking_store_path",
    "update_tracking_case_item_from_payload",
]
