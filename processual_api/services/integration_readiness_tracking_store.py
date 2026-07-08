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

# BEGIN INTEGRATION_READINESS_12A_CASE_MANAGEMENT_STORE

# 12A intentionally keeps this helper conservative:
# - same local JSON store family as 11P
# - safe case/list/detail exports
# - no customer endpoints
# - no raw credential persistence
# - no runtime connector execution

_json12a = __import__("json")
_os12a = __import__("os")
_deepcopy12a = __import__("copy").deepcopy
_datetime_module_12a = __import__("datetime", fromlist=["UTC", "datetime"])
_datetime12a = _datetime_module_12a.datetime
_UTC12A = _datetime_module_12a.UTC
_Path12a = __import__("pathlib", fromlist=["Path"]).Path

_ALLOWED_ITEM_STATUSES_12A = {"missing", "pending", "provided", "verified", "rejected"}
_ACTION_ITEM_STATUSES_12A = {"provided", "verified", "rejected"}

_DEFAULT_INPUT_ITEMS_12A = [
    {
        "item_key": "enterprise_core_api_reference",
        "label": "Enterprise core API reference",
        "status": "missing",
    },
    {
        "item_key": "sandbox_access_reference",
        "label": "Sandbox access reference",
        "status": "missing",
    },
    {
        "item_key": "auth_method_reference",
        "label": "Authentication method reference",
        "status": "missing",
    },
    {
        "item_key": "allowed_scopes_reference",
        "label": "Allowed API scopes reference",
        "status": "missing",
    },
    {
        "item_key": "rate_limits_reference",
        "label": "Rate limits reference",
        "status": "missing",
    },
    {
        "item_key": "test_account_reference",
        "label": "Test account reference",
        "status": "missing",
    },
]

_DEFAULT_SECURITY_ITEMS_12A = [
    {
        "item_key": "no_raw_secrets",
        "label": "No raw secrets supplied",
        "status": "verified",
    },
    {
        "item_key": "sandbox_before_production",
        "label": "Sandbox before production",
        "status": "missing",
    },
    {
        "item_key": "read_only_first",
        "label": "Read-only first integration posture",
        "status": "missing",
    },
    {
        "item_key": "supervisor_approval_required",
        "label": "Supervisor approval required",
        "status": "missing",
    },
]

_FORBIDDEN_REFERENCE_FRAGMENTS_12A = (
    "http" + "://",
    "https" + "://",
    "sk-",
    "secret",
    "password",
    "passwd",
    "token=",
    "api_key",
    "apikey",
    "bearer ",
    "authorization:",
)


def _utc_now_12a() -> str:
    return _datetime12a.now(_UTC12A).replace(microsecond=0).isoformat()


def _tracking_store_path_12a():
    env_path = _os12a.getenv("PMK_INTEGRATION_READINESS_CASES_PATH")
    if env_path:
        return _Path12a(env_path)

    for candidate_name in (
        "INTEGRATION_READINESS_CASES_PATH",
        "INTEGRATION_READINESS_TRACKING_STORE_PATH",
        "TRACKING_CASES_PATH",
        "DEFAULT_TRACKING_STORE_PATH",
    ):
        candidate = globals().get(candidate_name)
        if candidate:
            return _Path12a(candidate)

    return _Path12a("data") / "integration_readiness_cases.json"


def _read_tracking_payload_12a(path):
    if not path.exists():
        return {"cases": []}
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return {"cases": []}
    try:
        return _json12a.loads(raw)
    except _json12a.JSONDecodeError:
        return {"cases": []}


def _cases_from_payload_12a(payload):
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    cases = payload.get("cases")
    if isinstance(cases, list):
        return cases
    if isinstance(cases, dict):
        normalized = []
        for key, value in cases.items():
            if isinstance(value, dict):
                item = dict(value)
                item.setdefault("case_id", str(key))
                normalized.append(item)
        return normalized

    candidates = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        if "case_id" in value or "client_id" in value or "request_id" in value:
            item = dict(value)
            item.setdefault("case_id", str(key))
            candidates.append(item)
    return candidates


def _write_tracking_cases_12a(path, cases) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cases": cases,
        "guardrails": _guardrails_12a(),
        "updated_at": _utc_now_12a(),
    }
    path.write_text(
        _json12a.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _sanitize_text_12a(value, *, max_len: int = 240) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    lowered = text.lower()
    if any(fragment in lowered for fragment in _FORBIDDEN_REFERENCE_FRAGMENTS_12A):
        return ""
    return text[:max_len]


def _guardrails_12a() -> dict:
    return {
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_enabled": False,
        "raw_secret_visible": False,
    }


def _normalize_status_12a(value, *, action_only: bool = False) -> str:
    status = str(value or "").strip().lower()
    allowed = _ACTION_ITEM_STATUSES_12A if action_only else _ALLOWED_ITEM_STATUSES_12A
    if status not in allowed:
        raise ValueError(f"Unsupported readiness item status: {value!r}")
    return status


def _normalize_item_12a(item, index: int, prefix: str) -> dict:
    if isinstance(item, str):
        raw = {"item_key": item}
    elif isinstance(item, dict):
        raw = dict(item)
    else:
        raw = {}

    item_key = _sanitize_text_12a(
        raw.get("item_key")
        or raw.get("key")
        or raw.get("id")
        or f"{prefix}_{index + 1}",
        max_len=120,
    )
    if not item_key:
        item_key = f"{prefix}_{index + 1}"

    status = str(raw.get("status") or raw.get("state") or "missing").strip().lower()
    if status not in _ALLOWED_ITEM_STATUSES_12A:
        status = "missing"

    return {
        "item_key": item_key,
        "label": _sanitize_text_12a(
            raw.get("label") or raw.get("title") or item_key.replace("_", " ").title(),
            max_len=160,
        ),
        "status": status,
        "safe_reference": _sanitize_text_12a(
            raw.get("safe_reference") or raw.get("reference"),
        ),
        "note": _sanitize_text_12a(raw.get("note")),
        "updated_at": _sanitize_text_12a(raw.get("updated_at"), max_len=80),
    }


def _normalize_items_12a(value, defaults, prefix: str) -> list[dict]:
    source = value
    if isinstance(source, dict):
        source = [
            {"item_key": key, **(val if isinstance(val, dict) else {"status": val})}
            for key, val in source.items()
        ]

    if not isinstance(source, list) or not source:
        source = _deepcopy12a(defaults)

    return [
        _normalize_item_12a(item, index, prefix)
        for index, item in enumerate(source)
    ]


def _case_id_12a(raw: dict) -> str:
    case_id = _sanitize_text_12a(raw.get("case_id"), max_len=220)
    if case_id:
        return case_id

    client_id = _sanitize_text_12a(
        raw.get("client_id") or "unknown_client",
        max_len=80,
    )
    request_id = _sanitize_text_12a(
        raw.get("request_id") or "unknown_request",
        max_len=80,
    )
    adapter_id = _sanitize_text_12a(
        raw.get("adapter_id") or raw.get("integration_type") or "generic",
        max_len=80,
    )
    return f"{client_id}:{request_id}:{adapter_id}:readiness"


def _normalize_timeline_event_12a(event, index: int) -> dict:
    event_name = event.get("event") or event.get("type") or f"event_{index + 1}"
    return {
        "event": _sanitize_text_12a(event_name, max_len=120),
        "item_key": _sanitize_text_12a(event.get("item_key"), max_len=120),
        "status": _sanitize_text_12a(event.get("status"), max_len=40),
        "safe_reference": _sanitize_text_12a(event.get("safe_reference")),
        "note": _sanitize_text_12a(event.get("note")),
        "at": _sanitize_text_12a(
            event.get("at") or event.get("created_at"),
            max_len=80,
        ),
    }


def _normalize_case_12a(case) -> dict:
    raw = dict(case) if isinstance(case, dict) else {}
    case_id = _case_id_12a(raw)

    input_statuses = _normalize_items_12a(
        raw.get("input_statuses")
        or raw.get("inputs")
        or raw.get("required_inputs")
        or raw.get("provided_inputs"),
        _DEFAULT_INPUT_ITEMS_12A,
        "input",
    )
    security_control_statuses = _normalize_items_12a(
        raw.get("security_control_statuses")
        or raw.get("security_controls")
        or raw.get("controls"),
        _DEFAULT_SECURITY_ITEMS_12A,
        "security",
    )

    timeline = raw.get("timeline") or raw.get("timeline_events") or []
    if not isinstance(timeline, list):
        timeline = []

    normalized_timeline = [
        _normalize_timeline_event_12a(event, index)
        for index, event in enumerate(timeline)
        if isinstance(event, dict)
    ]

    guardrails = _guardrails_12a()

    return {
        "case_id": case_id,
        "client_id": _sanitize_text_12a(raw.get("client_id"), max_len=100),
        "request_id": _sanitize_text_12a(raw.get("request_id"), max_len=120),
        "adapter_id": _sanitize_text_12a(
            raw.get("adapter_id") or raw.get("integration_type"),
            max_len=120,
        ),
        "status": _sanitize_text_12a(
            raw.get("status") or "readiness_tracking",
            max_len=80,
        ),
        "input_statuses": input_statuses,
        "security_control_statuses": security_control_statuses,
        "timeline": normalized_timeline,
        **guardrails,
    }


def _count_status_12a(items, status: str) -> int:
    return sum(1 for item in items if item.get("status") == status)


def _case_summary_12a(case: dict) -> dict:
    inputs = case.get("input_statuses", [])
    controls = case.get("security_control_statuses", [])
    all_items = [*inputs, *controls]
    return {
        "case_id": case["case_id"],
        "client_id": case.get("client_id", ""),
        "request_id": case.get("request_id", ""),
        "adapter_id": case.get("adapter_id", ""),
        "status": case.get("status", ""),
        "provided_inputs": _count_status_12a(inputs, "provided"),
        "verified_items": _count_status_12a(all_items, "verified"),
        "rejected_items": _count_status_12a(all_items, "rejected"),
        "timeline_events": len(case.get("timeline", [])),
        **_guardrails_12a(),
    }


def _load_normalized_cases_12a() -> list[dict]:
    path = _tracking_store_path_12a()
    payload = _read_tracking_payload_12a(path)
    return [_normalize_case_12a(case) for case in _cases_from_payload_12a(payload)]


def list_tracking_cases_12a() -> dict:
    cases = _load_normalized_cases_12a()
    return {
        "cases": [_case_summary_12a(case) for case in cases],
        "persisted_cases": len(cases),
        **_guardrails_12a(),
    }


def build_tracking_case_detail_payload_12a(case_id: str) -> dict:
    target_id = str(case_id)
    for case in _load_normalized_cases_12a():
        if case.get("case_id") == target_id:
            return {
                "case": case,
                "case_id": case["case_id"],
                "input_statuses": case.get("input_statuses", []),
                "security_control_statuses": case.get(
                    "security_control_statuses",
                    [],
                ),
                "timeline": case.get("timeline", []),
                "summary": _case_summary_12a(case),
                **_guardrails_12a(),
            }
    raise KeyError(target_id)


def update_tracking_case_item_12a(
    case_id: str,
    item_key: str,
    status: str,
    safe_reference: str = "",
    note: str = "",
) -> dict:
    target_id = _sanitize_text_12a(case_id, max_len=220)
    target_item_key = _sanitize_text_12a(item_key, max_len=120)
    target_status = _normalize_status_12a(status, action_only=True)
    target_reference = _sanitize_text_12a(safe_reference)
    target_note = _sanitize_text_12a(note)

    if not target_id:
        raise ValueError("case_id is required")
    if not target_item_key:
        raise ValueError("item_key is required")

    path = _tracking_store_path_12a()
    cases = _load_normalized_cases_12a()

    target_case = None
    for case in cases:
        if case.get("case_id") == target_id:
            target_case = case
            break

    if target_case is None:
        raise KeyError(target_id)

    updated = False
    for collection_name in ("input_statuses", "security_control_statuses"):
        for item in target_case.get(collection_name, []):
            if item.get("item_key") != target_item_key:
                continue
            item["status"] = target_status
            item["safe_reference"] = target_reference
            item["note"] = target_note
            item["updated_at"] = _utc_now_12a()
            updated = True

    if not updated:
        target_case.setdefault("input_statuses", []).append(
            {
                "item_key": target_item_key,
                "label": target_item_key.replace("_", " ").title(),
                "status": target_status,
                "safe_reference": target_reference,
                "note": target_note,
                "updated_at": _utc_now_12a(),
            }
        )

    target_case.setdefault("timeline", []).append(
        {
            "event": f"item_{target_status}",
            "item_key": target_item_key,
            "status": target_status,
            "safe_reference": target_reference,
            "note": target_note,
            "at": _utc_now_12a(),
        }
    )

    _write_tracking_cases_12a(path, cases)
    return build_tracking_case_detail_payload_12a(target_id)
# END INTEGRATION_READINESS_12A_CASE_MANAGEMENT_STORE

# BEGIN INTEGRATION_READINESS_12A_SUMMARY_COMPAT

def build_tracking_summary_12a_compat() -> dict:
    cases = _load_normalized_cases_12a()

    provided_inputs = 0
    verified_items = 0
    rejected_items = 0
    timeline_events = 0

    for case in cases:
        input_items = case.get("input_statuses", [])
        security_items = case.get("security_control_statuses", [])
        all_items = [*input_items, *security_items]

        provided_inputs += _count_status_12a(input_items, "provided")
        verified_items += _count_status_12a(all_items, "verified")
        rejected_items += _count_status_12a(all_items, "rejected")
        timeline_events += len(case.get("timeline", []))

    tracking_foundation = 'available'

    return {
        "tracking_foundation": tracking_foundation,
        "tracking_store": True,
        "route_backed": True,
        "admin_tracking_summary": True,
        "case_management_12a_compatible": True,
        "persisted_cases": len(cases),
        "provided_inputs": provided_inputs,
        "verified_items": verified_items,
        "rejected_items": rejected_items,
        "timeline_events": timeline_events,
        **_guardrails_12a(),
    }
# END INTEGRATION_READINESS_12A_SUMMARY_COMPAT
