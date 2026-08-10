"""Governed external HTTP execution for Enterprise Integration sandbox proofs."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
import re
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from processual_api.integrations.enterprise_endpoint_bindings import (
    EndpointBindingError,
    EnterpriseEndpointBindingSpec,
    build_request_preview,
    map_response_to_task_input,
    validate_endpoint_binding,
)
from processual_api.integrations.integration_task_catalog import get_integration_task

MAX_SANDBOX_RESPONSE_BYTES = 1_048_576
_ALLOWED_CREDENTIAL_HEADERS = frozenset({"authorization", "x-api-key"})
_PROFILE_ENV_SAFE = re.compile(r"[^A-Z0-9]+")
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class SandboxExecutionError(ValueError):
    """A sandbox proof request was rejected without exposing secret material."""


@dataclass(frozen=True, slots=True)
class SandboxCredentialEnvelope:
    """Transient credential headers. Repr is deliberately redacted."""

    headers: dict[str, str]
    source: str

    def __repr__(self) -> str:  # pragma: no cover - defensive redaction
        return (
            "SandboxCredentialEnvelope(headers=<redacted>, "
            f"source={self.source!r})"
        )


class SandboxCredentialResolver(Protocol):
    async def resolve(
        self,
        *,
        credential_profile_id: str,
        binding_id: str,
    ) -> SandboxCredentialEnvelope: ...


class EnvironmentSandboxCredentialResolver:
    """Resolve sandbox credentials from deployment environment only."""

    @staticmethod
    def _suffix(profile_id: str) -> str:
        value = _PROFILE_ENV_SAFE.sub(
            "_",
            str(profile_id or "").strip().upper(),
        ).strip("_")
        if not value:
            raise SandboxExecutionError("credential_profile_id_invalid")
        return value

    async def resolve(
        self,
        *,
        credential_profile_id: str,
        binding_id: str,
    ) -> SandboxCredentialEnvelope:
        del binding_id
        suffix = self._suffix(credential_profile_id)
        authorization = os.getenv(
            f"MAESTRO_SANDBOX_AUTHORIZATION_{suffix}",
            "",
        ).strip()
        api_key = os.getenv(
            f"MAESTRO_SANDBOX_API_KEY_{suffix}",
            "",
        ).strip()

        headers: dict[str, str] = {}
        if authorization:
            headers["Authorization"] = authorization
        if api_key:
            headers["X-API-Key"] = api_key
        if not headers:
            raise SandboxExecutionError("sandbox_credential_reference_unresolved")
        return SandboxCredentialEnvelope(
            headers=headers,
            source="deployment_environment_reference",
        )


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_public_addresses_sync(hostname: str, port: int) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
    except OSError as exc:
        raise SandboxExecutionError("sandbox_destination_dns_failed") from exc
    addresses = tuple(
        sorted(
            {
                str(record[4][0]).split("%", 1)[0]
                for record in records
                if record and record[4]
            }
        )
    )
    if not addresses:
        raise SandboxExecutionError("sandbox_destination_dns_empty")
    if any(not _is_public_address(address) for address in addresses):
        raise SandboxExecutionError("sandbox_destination_not_public")
    return addresses


async def resolve_public_addresses(hostname: str, port: int) -> tuple[str, ...]:
    return await asyncio.to_thread(
        _resolve_public_addresses_sync,
        hostname,
        port,
    )


def _safe_credential_headers(envelope: SandboxCredentialEnvelope) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in envelope.headers.items():
        normalized = str(key or "").strip().lower()
        if normalized not in _ALLOWED_CREDENTIAL_HEADERS:
            raise SandboxExecutionError("sandbox_credential_header_not_allowed")
        if not str(value or "").strip():
            raise SandboxExecutionError("sandbox_credential_value_empty")
        safe[key] = str(value)
    if not safe:
        raise SandboxExecutionError("sandbox_credential_reference_unresolved")
    return safe


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _now_iso(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


async def execute_sandbox_binding(
    spec: EnterpriseEndpointBindingSpec,
    *,
    task_input: dict[str, Any],
    approved_operation_classes: set[str] | frozenset[str],
    approval_reference: str,
    request_body: dict[str, Any] | None = None,
    credential_resolver: SandboxCredentialResolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Execute one governed sandbox request and return redacted proof evidence."""

    validation = validate_endpoint_binding(spec)
    task = get_integration_task(spec.task_id)
    approval = str(approval_reference or "").strip()
    if not approval:
        raise SandboxExecutionError("sandbox_execution_approval_required")
    if task.operation_class not in approved_operation_classes:
        raise SandboxExecutionError("sandbox_operation_class_not_approved")
    if spec.environment != "sandbox":
        raise SandboxExecutionError("sandbox_environment_required")
    if request_body is not None and spec.method not in _BODY_METHODS:
        raise SandboxExecutionError("sandbox_request_body_method_not_allowed")
    if task.operation_class == "approval_gated_write" and request_body is None:
        raise SandboxExecutionError("sandbox_request_body_required")

    preview = build_request_preview(spec, task_input)
    parsed = httpx.URL(str(preview["url"]))
    if parsed.scheme != "https":
        raise SandboxExecutionError("sandbox_https_required")
    hostname = parsed.host
    if not hostname:
        raise SandboxExecutionError("sandbox_destination_host_required")
    port = int(parsed.port or 443)
    resolved_addresses = await resolve_public_addresses(hostname, port)

    resolver = credential_resolver or EnvironmentSandboxCredentialResolver()
    envelope = await resolver.resolve(
        credential_profile_id=spec.credential_profile_id,
        binding_id=spec.binding_id,
    )
    headers = {
        **{str(k): str(v) for k, v in spec.request_headers.items()},
        **_safe_credential_headers(envelope),
    }

    query = preview.get("query") or {}
    query_text = urlencode(query, doseq=True)
    request_url = str(preview["url"])
    if query_text:
        request_url = f"{request_url}?{query_text}"

    request_kwargs: dict[str, Any] = {"headers": headers}
    if request_body is not None:
        request_kwargs["json"] = request_body

    try:
        async with httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(float(spec.timeout_seconds)),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            response = await client.request(
                spec.method,
                request_url,
                **request_kwargs,
            )
    except httpx.HTTPError as exc:
        raise SandboxExecutionError("sandbox_http_request_failed") from exc

    if 300 <= response.status_code < 400:
        raise SandboxExecutionError("sandbox_redirect_blocked")
    content = bytes(response.content)
    if len(content) > MAX_SANDBOX_RESPONSE_BYTES:
        raise SandboxExecutionError("sandbox_response_too_large")
    if response.status_code not in spec.success_codes:
        raise SandboxExecutionError(
            f"sandbox_http_status_not_allowed:{response.status_code}"
        )

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
    if content_type and content_type not in {
        "application/json",
        "application/problem+json",
    }:
        raise SandboxExecutionError("sandbox_response_not_json")
    try:
        response_payload = response.json()
    except ValueError as exc:
        raise SandboxExecutionError("sandbox_response_json_invalid") from exc

    try:
        mapped = map_response_to_task_input(spec, response_payload)
    except EndpointBindingError as exc:
        raise SandboxExecutionError(str(exc)) from exc

    canonical_input = mapped["canonical_input"]
    completed_at = _now_iso(now)
    evidence_material = {
        "binding_id": spec.binding_id,
        "task_id": spec.task_id,
        "adapter_contract_id": spec.adapter_contract_id,
        "operation_class": task.operation_class,
        "required_scope_ids": validation["required_scope_ids"],
        "approval_reference": approval,
        "environment": "sandbox",
        "destination_host": hostname,
        "method": spec.method,
        "path": spec.path,
        "http_status": response.status_code,
        "content_type": content_type or "application/json",
        "response_sha256": hashlib.sha256(content).hexdigest(),
        "canonical_input_sha256": _digest(canonical_input),
        "request_body_sha256": _digest(request_body) if request_body is not None else None,
        "mapping_valid": True,
        "credential_source": envelope.source,
        "completed_at": completed_at,
    }

    return {
        "status": "sandbox_proof_passed",
        "environment": "sandbox",
        "binding_id": spec.binding_id,
        "task_id": spec.task_id,
        "adapter_contract_id": spec.adapter_contract_id,
        "operation_class": task.operation_class,
        "required_scope_ids": validation["required_scope_ids"],
        "output_slot": mapped["output_slot"],
        "canonical_input": canonical_input,
        "canonical_input_sha256": evidence_material["canonical_input_sha256"],
        "request_body_sha256": evidence_material["request_body_sha256"],
        "request_body_included_in_evidence": False,
        "http_status": response.status_code,
        "content_type": evidence_material["content_type"],
        "destination_host": hostname,
        "resolved_address_count": len(resolved_addresses),
        "response_sha256": evidence_material["response_sha256"],
        "approval_reference": approval,
        "credential_source": envelope.source,
        "credential_material_included": False,
        "raw_response_included": False,
        "redirects_followed": False,
        "mapping_valid": True,
        "network_request_executed": True,
        "evidence_sha256": _digest(evidence_material),
        "completed_at": completed_at,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "raw_secret_visible": False,
    }


__all__ = [
    "EnvironmentSandboxCredentialResolver",
    "MAX_SANDBOX_RESPONSE_BYTES",
    "SandboxCredentialEnvelope",
    "SandboxCredentialResolver",
    "SandboxExecutionError",
    "execute_sandbox_binding",
    "resolve_public_addresses",
]
