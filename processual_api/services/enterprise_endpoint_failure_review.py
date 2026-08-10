"""Reviewable, secret-free failure records for Enterprise sandbox execution.

Failure records use a closed taxonomy instead of persisting raw exception text.
They are intended to make customer and supervisor remediation deterministic:
where the run failed, what class of problem occurred, whether retry is useful,
and which corrective action should happen next.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

FAILURE_STORAGE_KEY = "enterprise_endpoint_sandbox_failures_v1"
MAX_FAILURE_RECORDS = 100

_FAILURE_CATALOG: tuple[
    tuple[tuple[str, ...], str, str, str, bool], ...
] = (
    (
        ("grant", "approval"),
        "authorization",
        "sandbox_grant_required",
        "Request or renew the supervisor sandbox execution grant.",
        True,
    ),
    (
        ("request body mapping", "request mapping"),
        "request_mapping",
        "request_mapping_invalid",
        "Review the outbound request mapping and required canonical inputs.",
        True,
    ),
    (
        ("task parameter", "path parameter"),
        "request_mapping",
        "request_parameter_missing",
        "Provide the missing task input or correct its path/query binding.",
        True,
    ),
    (
        ("dns",),
        "destination",
        "destination_dns_failed",
        "Verify the sandbox hostname and DNS configuration.",
        True,
    ),
    (
        (
            "destination_not_public",
            "destination not public",
            "localhost",
            "metadata",
        ),
        "destination",
        "destination_blocked",
        "Use an approved public HTTPS sandbox destination.",
        False,
    ),
    (
        ("https",),
        "destination",
        "https_required",
        "Configure an HTTPS sandbox endpoint.",
        False,
    ),
    (
        ("credential",),
        "credential",
        "credential_unavailable",
        "Verify the deployment credential reference and its sandbox scope.",
        True,
    ),
    (
        ("redirect",),
        "transport",
        "redirect_blocked",
        "Point the binding directly at the final sandbox resource without redirects.",
        True,
    ),
    (
        ("response_too_large", "response too large"),
        "response",
        "response_too_large",
        "Reduce the sandbox response size or narrow the endpoint payload.",
        True,
    ),
    (
        ("response_not_json", "json_invalid", "response json"),
        "response",
        "response_invalid",
        "Return valid JSON from the sandbox endpoint and verify Content-Type.",
        True,
    ),
    (
        ("http_status", "status_not_allowed"),
        "transport",
        "http_status_rejected",
        "Review the sandbox endpoint status and configured success codes.",
        True,
    ),
    (
        ("http_request_failed",),
        "transport",
        "transport_failed",
        "Check sandbox availability, TLS, timeout policy, and network reachability.",
        True,
    ),
    (
        ("response path", "mapped response", "mapping"),
        "response_mapping",
        "response_mapping_invalid",
        "Correct the response data path or canonical field mapping.",
        True,
    ),
    (
        ("task_injection", "canonical", "output slot"),
        "task_injection",
        "task_injection_invalid",
        "Review the canonical task schema and output-slot contract.",
        True,
    ),
)


def _now_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _reference(
    binding_id: str,
    task_id: str,
    attempt: int,
    occurred_at: str,
) -> str:
    material = f"{binding_id}|{task_id}|{attempt}|{occurred_at}".encode()
    return "sbf_" + hashlib.sha256(material).hexdigest()[:24]


def classify_sandbox_failure(exc: Exception) -> dict[str, Any]:
    """Map arbitrary internal failure text to a closed safe remediation taxonomy."""
    normalized = str(exc or "").strip().casefold().replace("-", "_")
    for markers, stage, code, action, retryable in _FAILURE_CATALOG:
        if any(marker in normalized for marker in markers):
            return {
                "stage": stage,
                "failure_code": code,
                "recommended_action": action,
                "retryable": retryable,
            }
    return {
        "stage": "execution",
        "failure_code": "sandbox_execution_failed",
        "recommended_action": (
            "Review the binding, grant, request/response mappings, "
            "and sandbox availability before retrying."
        ),
        "retryable": True,
    }


def list_safe_sandbox_failures(
    raw: dict[str, Any],
) -> list[dict[str, Any]]:
    items = raw.get(FAILURE_STORAGE_KEY, [])
    if not isinstance(items, list):
        return []
    results: list[dict[str, Any]] = []
    for item in items[-MAX_FAILURE_RECORDS:]:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "failure_id": str(item.get("failure_id") or ""),
                "binding_id": str(item.get("binding_id") or ""),
                "task_id": str(item.get("task_id") or ""),
                "stage": str(item.get("stage") or "execution"),
                "failure_code": str(
                    item.get("failure_code")
                    or "sandbox_execution_failed"
                ),
                "recommended_action": str(
                    item.get("recommended_action")
                    or "Review the sandbox configuration."
                ),
                "retryable": bool(item.get("retryable")),
                "status": str(item.get("status") or "open"),
                "attempt": int(item.get("attempt") or 1),
                "occurred_at": str(item.get("occurred_at") or ""),
                "last_reviewed_at": str(
                    item.get("last_reviewed_at") or ""
                ),
                "resolution_code": str(
                    item.get("resolution_code") or ""
                ),
                "resolved_at": str(item.get("resolved_at") or ""),
                "evidence_sha256": str(
                    item.get("evidence_sha256") or ""
                ),
                "production_allowed": False,
                "raw_secret_visible": False,
                "raw_error_included": False,
            }
        )
    return results


def record_sandbox_failure(
    raw: dict[str, Any],
    *,
    binding_id: str,
    task_id: str,
    exc: Exception,
    now: datetime | None = None,
) -> dict[str, Any]:
    safe = list_safe_sandbox_failures(raw)
    prior_attempts = [
        item
        for item in safe
        if item["binding_id"] == binding_id
        and item["task_id"] == task_id
    ]
    attempt = (
        max(
            (int(item["attempt"]) for item in prior_attempts),
            default=0,
        )
        + 1
    )
    classification = classify_sandbox_failure(exc)
    occurred_at = _now_iso(now)
    record = {
        "failure_id": _reference(
            binding_id,
            task_id,
            attempt,
            occurred_at,
        ),
        "binding_id": binding_id,
        "task_id": task_id,
        **classification,
        "status": "open",
        "attempt": attempt,
        "occurred_at": occurred_at,
        "last_reviewed_at": "",
        "resolution_code": "",
        "resolved_at": "",
        "evidence_sha256": "",
        "production_allowed": False,
        "raw_secret_visible": False,
        "raw_error_included": False,
    }
    safe.append(record)
    raw[FAILURE_STORAGE_KEY] = safe[-MAX_FAILURE_RECORDS:]
    return dict(record)


def resolve_failures_after_success(
    raw: dict[str, Any],
    *,
    binding_id: str,
    task_id: str,
    evidence_sha256: str,
    now: datetime | None = None,
) -> int:
    items = list_safe_sandbox_failures(raw)
    resolved_at = _now_iso(now)
    count = 0
    for item in items:
        if (
            item["binding_id"] == binding_id
            and item["task_id"] == task_id
            and item["status"] in {"open", "reviewing"}
        ):
            item["status"] = "resolved"
            item["resolution_code"] = "successful_sandbox_retest"
            item["resolved_at"] = resolved_at
            item["last_reviewed_at"] = resolved_at
            item["evidence_sha256"] = str(evidence_sha256 or "")
            count += 1
    raw[FAILURE_STORAGE_KEY] = items[-MAX_FAILURE_RECORDS:]
    return count


def mark_failure_reviewing(
    raw: dict[str, Any],
    *,
    failure_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    items = list_safe_sandbox_failures(raw)
    matches = [
        item
        for item in items
        if item["failure_id"] == failure_id
    ]
    if len(matches) != 1:
        raise ValueError("sandbox_failure_not_found")
    item = matches[0]
    if item["status"] == "resolved":
        raise ValueError("sandbox_failure_already_resolved")
    item["status"] = "reviewing"
    item["last_reviewed_at"] = _now_iso(now)
    raw[FAILURE_STORAGE_KEY] = items[-MAX_FAILURE_RECORDS:]
    return dict(item)


__all__ = [
    "FAILURE_STORAGE_KEY",
    "MAX_FAILURE_RECORDS",
    "classify_sandbox_failure",
    "list_safe_sandbox_failures",
    "mark_failure_reviewing",
    "record_sandbox_failure",
    "resolve_failures_after_success",
]
