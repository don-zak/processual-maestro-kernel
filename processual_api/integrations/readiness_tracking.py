from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

ITEM_STATUS_MISSING = "missing"
ITEM_STATUS_PROVIDED = "provided"
ITEM_STATUS_VERIFIED = "verified"
ITEM_STATUS_REJECTED = "rejected"

ALLOWED_ITEM_STATUSES = frozenset(
    {
        ITEM_STATUS_MISSING,
        ITEM_STATUS_PROVIDED,
        ITEM_STATUS_VERIFIED,
        ITEM_STATUS_REJECTED,
    }
)

SAFE_REFERENCE_TYPES = frozenset(
    {
        "document_ref",
        "ticket_ref",
        "vault_ref",
        "manual_note",
        "customer_portal_ref",
    }
)

FORBIDDEN_REFERENCE_MARKERS = (
    "password",
    "client_secret",
    "secret=",
    "token=",
    "api_key=",
    "bearer ",
    "http://",
    "https://",
    "-----begin",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _tuple_of_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _assert_safe_reference_text(value: str, field_name: str) -> None:
    lowered = value.lower()
    for marker in FORBIDDEN_REFERENCE_MARKERS:
        if marker in lowered:
            raise ValueError(f"{field_name} contains a forbidden reference marker")


def _assert_known_status(status: str) -> None:
    if status not in ALLOWED_ITEM_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_ITEM_STATUSES))
        raise ValueError(f"Unsupported readiness item status {status!r}; expected one of: {allowed}")


@dataclass(frozen=True)
class SafeEvidenceReference:
    reference_type: str
    reference_label: str

    def __post_init__(self) -> None:
        if self.reference_type not in SAFE_REFERENCE_TYPES:
            allowed = ", ".join(sorted(SAFE_REFERENCE_TYPES))
            raise ValueError(f"Unsupported safe reference type {self.reference_type!r}; expected one of: {allowed}")
        if not self.reference_label.strip():
            raise ValueError("safe reference label must not be empty")
        _assert_safe_reference_text(self.reference_label, "safe reference label")


@dataclass(frozen=True)
class ReadinessItemStatus:
    key: str
    status: str = ITEM_STATUS_MISSING
    safe_reference: SafeEvidenceReference | None = None
    verified_by: str | None = None
    verified_at: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("readiness item key must not be empty")
        _assert_known_status(self.status)
        if self.note:
            _assert_safe_reference_text(self.note, "readiness item note")
        if self.status == ITEM_STATUS_VERIFIED and not self.verified_by:
            raise ValueError("verified readiness items require verified_by")


@dataclass(frozen=True)
class ReadinessTimelineEvent:
    event_type: str
    actor: str
    safe_summary: str
    created_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise ValueError("timeline event type must not be empty")
        if not self.actor.strip():
            raise ValueError("timeline event actor must not be empty")
        if not self.safe_summary.strip():
            raise ValueError("timeline safe summary must not be empty")
        _assert_safe_reference_text(self.safe_summary, "timeline safe summary")


@dataclass(frozen=True)
class IntegrationReadinessCase:
    case_id: str
    client_id: str
    request_id: str
    adapter_contract_id: str
    credential_profile_id: str
    operational_profile_id: str = ""
    status: str = "blocked"
    input_statuses: tuple[ReadinessItemStatus, ...] = ()
    security_control_statuses: tuple[ReadinessItemStatus, ...] = ()
    timeline: tuple[ReadinessTimelineEvent, ...] = ()
    assigned_supervisor: str = ""
    sandbox_ready: bool = False
    production_allowed: bool = False
    runtime_connector_approved: bool = False
    external_http_enabled: bool = False
    raw_secret_visible: bool = False
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        required_fields = {
            "case_id": self.case_id,
            "client_id": self.client_id,
            "request_id": self.request_id,
            "adapter_contract_id": self.adapter_contract_id,
            "credential_profile_id": self.credential_profile_id,
        }
        for field_name, value in required_fields.items():
            if not value.strip():
                raise ValueError(f"{field_name} must not be empty")
            _assert_safe_reference_text(value, field_name)
        if self.production_allowed:
            raise ValueError("production approval cannot be enabled by readiness tracking")
        if self.runtime_connector_approved:
            raise ValueError("runtime connector approval cannot be enabled by readiness tracking")
        if self.external_http_enabled:
            raise ValueError("external HTTP cannot be enabled by readiness tracking")
        if self.raw_secret_visible:
            raise ValueError("raw secret visibility cannot be enabled by readiness tracking")


def build_case_id(client_id: str, request_id: str, readiness_check_id: str) -> str:
    safe_parts = (client_id.strip(), request_id.strip(), readiness_check_id.strip())
    for part in safe_parts:
        _assert_safe_reference_text(part, "case id component")
    return ":".join(safe_parts)


def readiness_case_from_check(
    readiness_check: Mapping[str, Any],
    *,
    client_id: str,
    request_id: str,
    operational_profile_id: str = "",
    assigned_supervisor: str = "",
) -> IntegrationReadinessCase:
    readiness_check_id = str(readiness_check.get("readiness_check_id", "")).strip()
    adapter_contract_id = str(readiness_check.get("adapter_contract_id", "")).strip()
    credential_profile_id = str(readiness_check.get("credential_profile_id", "")).strip()

    if not readiness_check_id:
        readiness_check_id = f"{adapter_contract_id}:{credential_profile_id}:readiness"

    missing_inputs = _tuple_of_strings(readiness_check.get("missing_inputs"))
    missing_security_controls = _tuple_of_strings(
        readiness_check.get("missing_security_controls")
    )

    input_statuses = tuple(
        ReadinessItemStatus(key=item, status=ITEM_STATUS_MISSING)
        for item in missing_inputs
    )
    security_control_statuses = tuple(
        ReadinessItemStatus(key=item, status=ITEM_STATUS_MISSING)
        for item in missing_security_controls
    )

    timeline = (
        ReadinessTimelineEvent(
            event_type="case_created",
            actor=assigned_supervisor or "system",
            safe_summary="Readiness tracking case created from declarative readiness check.",
        ),
    )

    return IntegrationReadinessCase(
        case_id=build_case_id(client_id, request_id, readiness_check_id),
        client_id=client_id,
        request_id=request_id,
        adapter_contract_id=adapter_contract_id,
        credential_profile_id=credential_profile_id,
        operational_profile_id=operational_profile_id,
        input_statuses=input_statuses,
        security_control_statuses=security_control_statuses,
        timeline=timeline,
        assigned_supervisor=assigned_supervisor,
    )


def _update_items(
    items: tuple[ReadinessItemStatus, ...],
    *,
    item_key: str,
    status: str,
    safe_reference: SafeEvidenceReference | None,
    actor: str,
    note: str,
) -> tuple[ReadinessItemStatus, ...]:
    _assert_known_status(status)
    updated: list[ReadinessItemStatus] = []
    matched = False

    for item in items:
        if item.key == item_key:
            matched = True
            updated.append(
                ReadinessItemStatus(
                    key=item.key,
                    status=status,
                    safe_reference=safe_reference,
                    verified_by=actor if status == ITEM_STATUS_VERIFIED else None,
                    verified_at=utc_now_iso() if status == ITEM_STATUS_VERIFIED else None,
                    note=note,
                )
            )
        else:
            updated.append(item)

    if not matched:
        updated.append(
            ReadinessItemStatus(
                key=item_key,
                status=status,
                safe_reference=safe_reference,
                verified_by=actor if status == ITEM_STATUS_VERIFIED else None,
                verified_at=utc_now_iso() if status == ITEM_STATUS_VERIFIED else None,
                note=note,
            )
        )

    return tuple(updated)


def _all_items_verified(items: tuple[ReadinessItemStatus, ...]) -> bool:
    return bool(items) and all(item.status == ITEM_STATUS_VERIFIED for item in items)


def _compute_sandbox_ready(case: IntegrationReadinessCase) -> bool:
    return _all_items_verified(case.input_statuses) and _all_items_verified(
        case.security_control_statuses
    )


def update_readiness_case_item(
    case: IntegrationReadinessCase,
    *,
    item_kind: str,
    item_key: str,
    status: str,
    actor: str,
    safe_reference: SafeEvidenceReference | None = None,
    note: str = "",
) -> IntegrationReadinessCase:
    if item_kind not in {"input", "security_control"}:
        raise ValueError("item_kind must be input or security_control")
    if not actor.strip():
        raise ValueError("actor must not be empty")
    if note:
        _assert_safe_reference_text(note, "readiness update note")

    if item_kind == "input":
        input_statuses = _update_items(
            case.input_statuses,
            item_key=item_key,
            status=status,
            safe_reference=safe_reference,
            actor=actor,
            note=note,
        )
        security_control_statuses = case.security_control_statuses
    else:
        input_statuses = case.input_statuses
        security_control_statuses = _update_items(
            case.security_control_statuses,
            item_key=item_key,
            status=status,
            safe_reference=safe_reference,
            actor=actor,
            note=note,
        )

    event = ReadinessTimelineEvent(
        event_type=f"{item_kind}_{status}",
        actor=actor,
        safe_summary=f"{item_kind} {item_key} marked as {status}.",
    )

    updated_case = replace(
        case,
        input_statuses=input_statuses,
        security_control_statuses=security_control_statuses,
        timeline=case.timeline + (event,),
        updated_at=utc_now_iso(),
    )

    return replace(
        updated_case,
        sandbox_ready=_compute_sandbox_ready(updated_case),
        status="sandbox_ready" if _compute_sandbox_ready(updated_case) else "blocked",
        production_allowed=False,
        runtime_connector_approved=False,
        external_http_enabled=False,
        raw_secret_visible=False,
    )


def readiness_case_summary(case: IntegrationReadinessCase) -> dict[str, Any]:
    all_items = case.input_statuses + case.security_control_statuses
    status_counts = {status: 0 for status in sorted(ALLOWED_ITEM_STATUSES)}
    for item in all_items:
        status_counts[item.status] += 1

    return {
        "case_id": case.case_id,
        "client_id": case.client_id,
        "request_id": case.request_id,
        "adapter_contract_id": case.adapter_contract_id,
        "credential_profile_id": case.credential_profile_id,
        "operational_profile_id": case.operational_profile_id,
        "status": case.status,
        "inputs_total": len(case.input_statuses),
        "security_controls_total": len(case.security_control_statuses),
        "status_counts": status_counts,
        "sandbox_ready": case.sandbox_ready,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_enabled": False,
        "raw_secret_visible": False,
        "timeline_events": len(case.timeline),
    }


__all__ = [
    "ALLOWED_ITEM_STATUSES",
    "ITEM_STATUS_MISSING",
    "ITEM_STATUS_PROVIDED",
    "ITEM_STATUS_REJECTED",
    "ITEM_STATUS_VERIFIED",
    "SAFE_REFERENCE_TYPES",
    "IntegrationReadinessCase",
    "ReadinessItemStatus",
    "ReadinessTimelineEvent",
    "SafeEvidenceReference",
    "readiness_case_from_check",
    "readiness_case_summary",
    "update_readiness_case_item",
]

