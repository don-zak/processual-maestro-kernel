"""Bounded read-only executor for Controlled Real Pilot.

This service is intentionally not registered on any HTTP router. It can only be
invoked by future operator-controlled code after the separate Controlled Real
Pilot admission gate succeeds. External Evaluation credentials are not accepted
or interpreted here.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx

from processual_api.services.controlled_real_pilot import (
    ControlledRealPilotAdmissionError,
    ControlledRealPilotGrant,
    admit_controlled_real_pilot_request,
)

_MAX_RESPONSE_BYTES = 262_144
_ALLOWED_CREDENTIAL_HEADERS = frozenset({"authorization", "x-api-key"})


class ControlledRealPilotReadError(ValueError):
    """A controlled real-system read was rejected before unsafe processing."""


def _safe_credentials(headers: dict[str, str] | None) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in (headers or {}).items():
        normalized = str(key or "").strip().lower()
        if normalized not in _ALLOWED_CREDENTIAL_HEADERS:
            raise ControlledRealPilotReadError("controlled_real_pilot_credential_header_not_allowed")
        text = str(value or "").strip()
        if not text:
            raise ControlledRealPilotReadError("controlled_real_pilot_credential_value_empty")
        safe[str(key)] = text
    return safe


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def execute_controlled_real_read(
    grant: ControlledRealPilotGrant,
    *,
    task_id: str,
    binding_id: str,
    destination_host: str,
    resource_id: str,
    path: str,
    credential_headers: dict[str, str] | None = None,
    transport: httpx.AsyncBaseTransport,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """Execute one exact GET after fail-closed admission and return safe evidence.

    The caller must provide a peer-verifying transport. The transport must expose
    ``last_verified_peer`` after a successful request; otherwise the operation is
    rejected even when the HTTP response itself succeeds.
    """

    try:
        admission = admit_controlled_real_pilot_request(
            grant,
            task_id=task_id,
            binding_id=binding_id,
            destination_host=destination_host,
            method="GET",
            operation_class=grant.operation_class,
            resource_id=resource_id,
            changed_fields=set(),
            requested_mutations=0,
            supervisor_approval_reference=None,
        )
    except ControlledRealPilotAdmissionError as exc:
        raise ControlledRealPilotReadError(str(exc)) from exc

    normalized_path = str(path or "").strip()
    if not normalized_path.startswith("/") or normalized_path.startswith("//"):
        raise ControlledRealPilotReadError("controlled_real_pilot_path_invalid")
    if "?" in normalized_path or "#" in normalized_path:
        raise ControlledRealPilotReadError("controlled_real_pilot_query_or_fragment_not_allowed")

    host = str(destination_host or "").strip().lower()
    url = f"https://{host}{normalized_path}"
    headers = _safe_credentials(credential_headers)

    try:
        async with httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(float(timeout_seconds)),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ControlledRealPilotReadError("controlled_real_pilot_http_request_failed") from exc

    if 300 <= response.status_code < 400:
        raise ControlledRealPilotReadError("controlled_real_pilot_redirect_blocked")
    if response.status_code < 200 or response.status_code >= 300:
        raise ControlledRealPilotReadError(
            f"controlled_real_pilot_http_status_not_allowed:{response.status_code}"
        )

    peer = str(getattr(transport, "last_verified_peer", "") or "").strip()
    if not peer:
        raise ControlledRealPilotReadError("controlled_real_pilot_peer_unverified")

    content = bytes(response.content)
    if len(content) > _MAX_RESPONSE_BYTES:
        raise ControlledRealPilotReadError("controlled_real_pilot_response_too_large")

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "application/problem+json"}:
        raise ControlledRealPilotReadError("controlled_real_pilot_response_not_json")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ControlledRealPilotReadError("controlled_real_pilot_response_json_invalid") from exc

    response_sha256 = _sha256_bytes(content)
    payload_sha256 = _sha256_json(payload)
    evidence = {
        "grant_id": grant.grant_id,
        "task_id": grant.task_id,
        "binding_id": grant.binding_id,
        "destination_host": host,
        "resource_id": resource_id,
        "method": "GET",
        "operation_class": grant.operation_class,
        "http_status": int(response.status_code),
        "verified_peer": peer,
        "response_sha256": response_sha256,
        "payload_sha256": payload_sha256,
        "production_read_performed": True,
        "production_mutation_performed": False,
        "raw_response_included": False,
        "credential_material_included": False,
        "external_evaluation_authority_reused": False,
    }
    evidence_sha256 = _sha256_json(evidence)

    return {
        "status": "controlled_real_pilot_read_succeeded",
        "admission": admission,
        "http_status": int(response.status_code),
        "destination_host": host,
        "verified_peer": peer,
        "response_sha256": response_sha256,
        "payload_sha256": payload_sha256,
        "evidence_sha256": evidence_sha256,
        "raw_response_included": False,
        "credential_material_included": False,
        "production_read_performed": True,
        "production_mutation_performed": False,
        "external_evaluation_authority_reused": False,
    }


__all__ = [
    "ControlledRealPilotReadError",
    "execute_controlled_real_read",
]
