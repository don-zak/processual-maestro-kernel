"""Reference-only intake preview for Pilot Handoff 17C-R1.

The preview validates a sandbox integration manifest without persisting it,
resolving credentials, contacting external systems, or granting authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

MANIFEST_VERSION = "pilot-handoff-intake-17c-r1"

_ALLOWED_TOP_LEVEL_FIELDS = {
    "manifest_version",
    "organization",
    "integration",
    "network_security",
    "operations",
    "governance",
    "evidence_refs",
}

_REQUIRED_PATHS = (
    "manifest_version",
    "organization.organization_id",
    "organization.display_name",
    "organization.sector",
    "organization.technical_contact_ref",
    "integration.adapter_contract_id",
    "integration.credential_profile_id",
    "integration.target_environment",
    "integration.api_documentation_ref",
    "integration.sandbox_base_url_ref",
    "integration.authentication_method",
    "integration.requested_scopes",
    "integration.sample_payload_refs",
    "network_security.dns_names",
    "network_security.tls_min_version",
    "network_security.outbound_allowlist_refs",
    "operations.rate_limit_ref",
    "operations.support_contact_ref",
    "operations.maintenance_window_ref",
    "governance.data_classification",
    "governance.retention_policy_ref",
    "governance.incident_contact_ref",
    "evidence_refs",
)

_PROHIBITED_KEY_FRAGMENTS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
}

_PROHIBITED_VALUE_MARKERS = (
    "-----begin private key-----",
    "-----begin rsa private key-----",
    "bearer ",
)


class IntakePreviewValidationError(ValueError):
    """Raised when an intake manifest violates the safe preview contract."""


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True


def _value_at_path(payload: Mapping[str, object], path: str) -> object:
    value: object = payload
    for segment in path.split("."):
        if not isinstance(value, Mapping) or segment not in value:
            return None
        value = value[segment]
    return value


def _scan_for_prohibited_content(value: object, path: str = "manifest") -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key).strip().lower()
            normalized_key = key.replace("-", "_").replace(" ", "_")
            if any(fragment in normalized_key for fragment in _PROHIBITED_KEY_FRAGMENTS):
                raise IntakePreviewValidationError(
                    f"prohibited secret-bearing field at {path}.{raw_key}"
                )
            _scan_for_prohibited_content(child, f"{path}.{raw_key}")
        return

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            _scan_for_prohibited_content(child, f"{path}[{index}]")
        return

    if isinstance(value, str):
        lowered = value.strip().lower()
        if any(marker in lowered for marker in _PROHIBITED_VALUE_MARKERS):
            raise IntakePreviewValidationError(
                f"prohibited credential-like value at {path}"
            )


def _manifest_digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _review_queue(payload: Mapping[str, object]) -> list[dict[str, str]]:
    return [
        {
            "review": "Identity and ownership",
            "owner": "Integration supervisor",
            "status": "pending_review",
        },
        {
            "review": "API contract and scopes",
            "owner": "Solution architect",
            "status": "pending_review",
        },
        {
            "review": "Network and TLS controls",
            "owner": "Security and network",
            "status": "pending_review",
        },
        {
            "review": "Operations and pilot acceptance",
            "owner": "Pilot owner",
            "status": "pending_review",
        },
    ]


def build_operator_pilot_handoff_intake_preview(
    raw_manifest: Mapping[str, Any],
) -> dict[str, object]:
    """Validate and score a reference-only sandbox integration manifest."""
    if not isinstance(raw_manifest, Mapping):
        raise IntakePreviewValidationError("manifest must be a JSON object")

    unknown_fields = sorted(set(raw_manifest) - _ALLOWED_TOP_LEVEL_FIELDS)
    if unknown_fields:
        raise IntakePreviewValidationError(
            "unknown top-level fields: " + ", ".join(unknown_fields)
        )

    _scan_for_prohibited_content(raw_manifest)

    if raw_manifest.get("manifest_version") != MANIFEST_VERSION:
        raise IntakePreviewValidationError(
            f"manifest_version must be {MANIFEST_VERSION}"
        )

    target_environment = _value_at_path(raw_manifest, "integration.target_environment")
    if str(target_environment).strip().lower() != "sandbox":
        raise IntakePreviewValidationError(
            "target environment must remain sandbox during intake preview"
        )

    missing_fields = [
        path for path in _REQUIRED_PATHS if not _is_present(_value_at_path(raw_manifest, path))
    ]
    received_count = len(_REQUIRED_PATHS) - len(missing_fields)
    completeness_percent = round(received_count * 100 / len(_REQUIRED_PATHS))
    status = "ready_for_supervisor_review" if not missing_fields else "needs_input"

    return {
        "schema_version": MANIFEST_VERSION,
        "status": status,
        "completeness_percent": completeness_percent,
        "required_count": len(_REQUIRED_PATHS),
        "received_count": received_count,
        "missing_fields": missing_fields,
        "manifest_digest": _manifest_digest(raw_manifest),
        "review_queue": _review_queue(raw_manifest),
        "warnings": [
            "References are reviewed; referenced systems are not contacted.",
            "No credential value may be included in the manifest.",
            "A complete preview does not authorize sandbox or production execution.",
        ],
        "next_action": (
            "Supervisor reviews references and evidence before sandbox qualification."
            if not missing_fields
            else "Organization supplies the missing reference fields for a new preview."
        ),
        "persisted": False,
        "review_only": True,
        "guardrails": {
            "production_allowed": False,
            "runtime_connector_approved": False,
            "customer_credentials_present": False,
            "external_http_allowed": False,
            "automatic_activation_allowed": False,
            "credentials_storage_allowed": False,
        },
    }
