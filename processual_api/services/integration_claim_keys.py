"""Supervisor-issued integration claim keys for 13A.

These keys are onboarding claims only. They never enable runtime connectors,
production access, external HTTP, or raw secret visibility.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

GUARDRAILS: dict[str, bool] = {
    "runtime_enabled": False,
    "production_allowed": False,
    "external_http_enabled": False,
    "raw_secret_visible": False,
}

OPERATOR_REQUIRED_INPUTS: list[str] = [
    "operator_api_documentation_reference",
    "sandbox_endpoint_reference",
    "auth_method_reference",
    "allowed_scopes_matrix",
    "rate_limit_policy",
    "test_account_reference",
    "incident_escalation_path",
    "production_approval_path",
]

DEFAULT_ALLOWED_ADAPTER_FAMILIES: list[str] = [
    "crm",
    "billing",
    "ticketing",
    "order_management",
    "network_assurance",
    "document",
    "generic_enterprise_helpdesk",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _store_path() -> Path:
    override = os.environ.get("PMK_INTEGRATION_CLAIM_KEYS_STORE")
    if override:
        return Path(override)
    return _project_root() / "data" / "integration_claim_keys.json"


def _audit_path() -> Path:
    override = os.environ.get("PMK_ADMIN_AUDIT_EVENTS_PATH")
    if override:
        return Path(override)
    return _project_root() / "data" / "admin_audit_events.jsonl"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _new_store() -> dict[str, Any]:
    return {
        "version": "integration-claim-keys-13a",
        "claim_keys": [],
        "onboarding_cases": [],
    }


def _load_store() -> dict[str, Any]:
    path = _store_path()
    if not path.exists():
        return _new_store()
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        loaded = _new_store()

    if not isinstance(loaded, dict):
        loaded = _new_store()

    loaded.setdefault("version", "integration-claim-keys-13a")
    loaded.setdefault("claim_keys", [])
    loaded.setdefault("onboarding_cases", [])
    return loaded


def _save_store(store: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(store, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _append_audit_event(event_type: str, **payload: Any) -> None:
    path = _audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": event_type,
        "event_type": event_type,
        "at": _iso(_utcnow()),
        **payload,
        **GUARDRAILS,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def _clean_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _clean_list(value: Any, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else list(default or [])
    if isinstance(value, (list, tuple, set)):
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned or list(default or [])
    return list(default or [])


def _hash_claim_key(raw_claim_key: str) -> str:
    return hashlib.sha256(raw_claim_key.encode("utf-8")).hexdigest()


def _mask_claim_key(claim_key_id: str) -> str:
    return f"{claim_key_id}.************************"


def _sanitize_claim(record: dict[str, Any]) -> dict[str, Any]:
    safe = dict(record)
    safe.pop("claim_key_hash", None)
    safe.pop("claim_key_once", None)
    safe["masked_claim_key"] = _mask_claim_key(str(record.get("claim_key_id", "ick_unknown")))
    safe.update(GUARDRAILS)
    return safe


def _find_claim_by_id(store: dict[str, Any], claim_key_id: str) -> dict[str, Any] | None:
    for record in store.get("claim_keys", []):
        if record.get("claim_key_id") == claim_key_id:
            return record
    return None


def _find_claim_by_raw_key(store: dict[str, Any], raw_claim_key: str) -> dict[str, Any] | None:
    claim_hash = _hash_claim_key(raw_claim_key)
    for record in store.get("claim_keys", []):
        if record.get("claim_key_hash") == claim_hash:
            return record
    return None


def _is_expired(record: dict[str, Any]) -> bool:
    expires_at = _parse_datetime(record.get("expires_at"))
    if not expires_at:
        return False
    return expires_at <= _utcnow()


def issue_integration_claim_key(
    payload: dict[str, Any] | None,
    *,
    issued_by: str = "supervisor",
) -> dict[str, Any]:
    """Issue a one-time onboarding claim key and return the raw value once."""

    payload = payload or {}
    now = _utcnow()
    expires_at = _clean_string(payload.get("expires_at"))
    if not expires_at:
        expires_at = _iso(now + timedelta(days=14))

    client_id = _clean_string(payload.get("client_id"), "pending-client")
    issued_to = _clean_string(payload.get("issued_to"), "operator-integration-officer")
    operator_org_id = _clean_string(payload.get("operator_org_id"), client_id)

    claim_key_id = "ick_" + uuid.uuid4().hex[:16]
    secret_value = secrets.token_urlsafe(32)
    raw_claim_key = f"{claim_key_id}.{secret_value}"

    record: dict[str, Any] = {
        "claim_key_id": claim_key_id,
        "client_id": client_id,
        "issued_to": issued_to,
        "operator_org_id": operator_org_id,
        "allowed_adapter_families": _clean_list(
            payload.get("allowed_adapter_families"),
            DEFAULT_ALLOWED_ADAPTER_FAMILIES,
        ),
        "allowed_domains": _clean_list(payload.get("allowed_domains"), ["telecom"]),
        "expires_at": expires_at,
        "one_time_use": bool(payload.get("one_time_use", True)),
        "runtime_enabled": False,
        "production_allowed": False,
        "revoked": False,
        "status": "claim_issued",
        "claimed_at": None,
        "claimed_by": None,
        "issued_at": _iso(now),
        "issued_by": issued_by,
        "claim_key_hash": _hash_claim_key(raw_claim_key),
        "pilot_terms_note": _clean_string(payload.get("pilot_terms_note")),
        "public_reason_for_client": "",
        "internal_reason_for_supervisor": "",
    }

    store = _load_store()
    store["claim_keys"].append(record)
    _save_store(store)

    _append_audit_event(
        "integration_claim_key_issued",
        claim_key_id=claim_key_id,
        client_id=client_id,
        operator_org_id=operator_org_id,
        issued_to=issued_to,
        issued_by=issued_by,
        raw_secret_visible=False,
    )

    return {
        "package_version": "integration-claim-keys-13a",
        "claim_key_once": raw_claim_key,
        "raw_claim_key_visible_once": True,
        "claim_key": _sanitize_claim(record),
        "guardrails": dict(GUARDRAILS),
    }


def list_integration_claim_keys() -> dict[str, Any]:
    store = _load_store()
    claims = [_sanitize_claim(record) for record in store.get("claim_keys", [])]
    return {
        "package_version": "integration-claim-keys-13a",
        "claim_keys": claims,
        "claim_key_count": len(claims),
        "guardrails": dict(GUARDRAILS),
    }


def revoke_integration_claim_key(
    claim_key_id: str,
    *,
    revoked_by: str = "supervisor",
    reason: str = "",
) -> dict[str, Any]:
    store = _load_store()
    record = _find_claim_by_id(store, claim_key_id)
    if not record:
        return {
            "ok": False,
            "error": "claim_key_not_found",
            "claim_key_id": claim_key_id,
            "guardrails": dict(GUARDRAILS),
        }

    record["revoked"] = True
    record["status"] = "revoked"
    record["revoked_at"] = _iso(_utcnow())
    record["revoked_by"] = revoked_by
    record["public_reason_for_client"] = reason or "Integration onboarding claim was revoked by supervisor."
    record["internal_reason_for_supervisor"] = reason

    _save_store(store)

    _append_audit_event(
        "integration_claim_key_revoked",
        claim_key_id=claim_key_id,
        client_id=record.get("client_id"),
        operator_org_id=record.get("operator_org_id"),
        revoked_by=revoked_by,
        reason=reason,
    )

    return {
        "ok": True,
        "claim_key": _sanitize_claim(record),
        "guardrails": dict(GUARDRAILS),
    }


def redeem_integration_claim_key(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    raw_claim_key = _clean_string(payload.get("claim_key") or payload.get("integration_claim_key"))
    client_id = _clean_string(payload.get("client_id"), "pending-client")
    user_id = _clean_string(payload.get("user_id"), "operator-user")
    operator_identity = _clean_string(
        payload.get("integration_officer_identity"),
        user_id,
    )

    if not raw_claim_key:
        return {
            "ok": False,
            "error": "missing_claim_key",
            "guardrails": dict(GUARDRAILS),
        }

    store = _load_store()
    record = _find_claim_by_raw_key(store, raw_claim_key)

    if not record:
        return {
            "ok": False,
            "error": "invalid_claim_key",
            "guardrails": dict(GUARDRAILS),
        }

    if record.get("revoked"):
        return {
            "ok": False,
            "error": "claim_key_revoked",
            "claim_key": _sanitize_claim(record),
            "guardrails": dict(GUARDRAILS),
        }

    if _is_expired(record):
        record["status"] = "expired"
        _save_store(store)
        return {
            "ok": False,
            "error": "claim_key_expired",
            "claim_key": _sanitize_claim(record),
            "guardrails": dict(GUARDRAILS),
        }

    if record.get("one_time_use") and record.get("claimed_at"):
        return {
            "ok": False,
            "error": "claim_key_already_used",
            "claim_key": _sanitize_claim(record),
            "guardrails": dict(GUARDRAILS),
        }

    now = _utcnow()
    case_id = "onb_" + uuid.uuid4().hex[:16]

    record["claimed_at"] = _iso(now)
    record["claimed_by"] = user_id
    record["client_id"] = client_id or record.get("client_id")
    record["status"] = "claimed"

    onboarding_case = {
        "case_id": case_id,
        "source": "integration_claim_key",
        "claim_key_id": record.get("claim_key_id"),
        "client_id": record.get("client_id"),
        "user_id": user_id,
        "operator_org_id": record.get("operator_org_id"),
        "integration_officer_identity": operator_identity,
        "status": "onboarding_in_progress",
        "required_inputs": list(OPERATOR_REQUIRED_INPUTS),
        "provided_inputs": {},
        "created_at": _iso(now),
        "updated_at": _iso(now),
        "runtime_enabled": False,
        "production_allowed": False,
        "external_http_enabled": False,
        "raw_secret_visible": False,
    }

    store["onboarding_cases"].append(onboarding_case)
    _save_store(store)

    _append_audit_event(
        "integration_claim_key_redeemed",
        claim_key_id=record.get("claim_key_id"),
        case_id=case_id,
        client_id=record.get("client_id"),
        user_id=user_id,
        operator_org_id=record.get("operator_org_id"),
    )

    return {
        "ok": True,
        "claim_key": _sanitize_claim(record),
        "onboarding_case": onboarding_case,
        "guardrails": dict(GUARDRAILS),
    }


def get_client_integration_onboarding_status(
    *,
    client_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    store = _load_store()
    client_id = _clean_string(client_id)
    user_id = _clean_string(user_id)

    cases = []
    for case in store.get("onboarding_cases", []):
        if client_id and case.get("client_id") != client_id:
            continue
        if user_id and case.get("user_id") != user_id:
            continue
        cases.append({**case, **GUARDRAILS})

    claims = []
    for record in store.get("claim_keys", []):
        if client_id and record.get("client_id") != client_id:
            continue
        claims.append(_sanitize_claim(record))

    return {
        "package_version": "integration-claim-keys-13a",
        "status": "onboarding_available" if cases else "no_onboarding_case",
        "client_id": client_id,
        "user_id": user_id,
        "claim_keys": claims,
        "onboarding_cases": cases,
        "onboarding_case_count": len(cases),
        "operator_required_inputs": list(OPERATOR_REQUIRED_INPUTS),
        "guardrails": dict(GUARDRAILS),
    }
