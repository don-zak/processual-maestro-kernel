"""Create a safe Stage 18 enterprise-to-R10 metadata binding.

This service resolves all authoritative resources internally. It does not
issue or redeem keys, execute connectors, contact external services, or store
credential material.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from processual_api.integrations.connector_registry import (
    get_runtime_connector_contract,
)
from processual_api.services.enterprise_external_connectivity_adapter_18 import (
    EnterpriseR10BindingError,
    build_enterprise_r10_binding_plan,
)
from processual_api.services.enterprise_qualification_18 import (
    QualificationGrant,
    get_task_execution_policy,
)
from processual_api.services.enterprise_qualification_store_18 import (
    load_qualification_store,
)
from processual_api.services.enterprise_r10_binding_store_18 import (
    EnterpriseR10BindingStoreError,
    record_enterprise_r10_binding,
)
from processual_api.services.external_connectivity_intake import (
    get_external_connectivity_case,
)


class EnterpriseR10BindingCreationError(ValueError):
    """Safe rejection from the binding-creation orchestration."""


def _required_identifier(
    field_name: str,
    value: Any,
) -> str:
    normalized = str(value or "").strip()

    if not normalized:
        raise EnterpriseR10BindingCreationError(
            f"{field_name}_required"
        )

    return normalized


def _active_grant(
    *,
    case_id: str,
    client_id: str,
    qualification_store_path: Path | None,
) -> QualificationGrant:
    store = load_qualification_store(
        qualification_store_path
    )

    matches = [
        item
        for item in store["grants"]
        if isinstance(item, dict)
        and item.get("case_id") == case_id
        and item.get("client_id") == client_id
        and item.get("status") == "activated"
    ]

    if not matches:
        raise EnterpriseR10BindingCreationError(
            "activated_qualification_grant_not_found"
        )

    if len(matches) > 1:
        raise EnterpriseR10BindingCreationError(
            "multiple_activated_qualification_grants"
        )

    record = matches[0]

    expires_at_raw = str(
        record.get("expires_at") or ""
    ).strip()

    try:
        expires_at = datetime.fromisoformat(
            expires_at_raw.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise EnterpriseR10BindingCreationError(
            "qualification_grant_expiry_invalid"
        ) from exc

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)

    if expires_at <= datetime.now(UTC):
        raise EnterpriseR10BindingCreationError(
            "qualification_grant_expired"
        )

    try:
        return QualificationGrant(
            grant_id=_required_identifier(
                "grant_id",
                record.get("grant_id"),
            ),
            case_id=_required_identifier(
                "grant_case_id",
                record.get("case_id"),
            ),
            client_id=_required_identifier(
                "grant_client_id",
                record.get("client_id"),
            ),
            integration_track=_required_identifier(
                "grant_integration_track",
                record.get("integration_track"),
            ),
            approved_task_ids=tuple(
                str(value or "").strip()
                for value in (
                    record.get("approved_task_ids") or []
                )
                if str(value or "").strip()
            ),
            approved_profile_ids=tuple(
                str(value or "").strip()
                for value in (
                    record.get("approved_profile_ids") or []
                )
                if str(value or "").strip()
            ),
            issued_by_supervisor_id=_required_identifier(
                "issued_by_supervisor_id",
                record.get("issued_by_supervisor_id"),
            ),
            supervisor_session_key_id=_required_identifier(
                "supervisor_session_key_id",
                record.get("supervisor_session_key_id"),
            ),
            issued_at=_required_identifier(
                "issued_at",
                record.get("issued_at"),
            ),
            expires_at=expires_at_raw,
            status="activated",
            environment=str(
                record.get("environment") or ""
            ),
            revision=int(record.get("revision") or 1),
            constraints=tuple(
                str(value or "").strip()
                for value in (
                    record.get("constraints") or []
                )
                if str(value or "").strip()
            ),
            production_allowed=bool(
                record.get("production_allowed")
            ),
            runtime_connector_approved=bool(
                record.get(
                    "runtime_connector_approved"
                )
            ),
            write_allowed=bool(
                record.get("write_allowed")
            ),
            restricted_allowed=bool(
                record.get("restricted_allowed")
            ),
            external_http_allowed=bool(
                record.get("external_http_allowed")
            ),
            raw_secret_visible=bool(
                record.get("raw_secret_visible")
            ),
        )
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise EnterpriseR10BindingCreationError(
            "qualification_grant_contract_invalid"
        ) from exc


def create_enterprise_r10_binding(
    *,
    institution_case: dict[str, Any],
    institution_task_id: str,
    client_id: str,
    external_connectivity_case_id: str,
    actor: str,
    qualification_store_path: Path | None = None,
    external_case_store_path: Path | None = None,
    binding_store_path: Path | None = None,
) -> dict[str, Any]:
    """Resolve, validate, and persist one secret-free R10 binding."""
    case_id = _required_identifier(
        "institution_case_id",
        institution_case.get("case_id"),
    )
    case_client_id = _required_identifier(
        "institution_case_client_id",
        institution_case.get("client_id"),
    )
    client_id = _required_identifier(
        "client_id",
        client_id,
    )
    task_id = _required_identifier(
        "institution_task_id",
        institution_task_id,
    )
    external_case_id = _required_identifier(
        "external_connectivity_case_id",
        external_connectivity_case_id,
    )
    actor = _required_identifier("actor", actor)

    if client_id != case_client_id:
        raise EnterpriseR10BindingCreationError(
            "institution_case_client_mismatch"
        )

    grant = _active_grant(
        case_id=case_id,
        client_id=client_id,
        qualification_store_path=(
            qualification_store_path
        ),
    )

    policy = get_task_execution_policy(
        str(
            institution_case.get(
                "integration_track"
            )
            or ""
        ),
        task_id,
    )

    if not policy.connector_id:
        raise EnterpriseR10BindingCreationError(
            "task_connector_missing"
        )

    try:
        connector = get_runtime_connector_contract(
            policy.connector_id
        )
    except KeyError as exc:
        raise EnterpriseR10BindingCreationError(
            "task_connector_not_registered"
        ) from exc

    connector_scope_ids = tuple(
        capability.scope_id
        for capability in connector.capabilities
        if capability.access_mode == "read"
    )

    requested_scope_ids = tuple(
        policy.allowed_scope_ids
    )

    if not requested_scope_ids:
        raise EnterpriseR10BindingCreationError(
            "task_policy_scope_missing"
        )

    try:
        external_case = (
            get_external_connectivity_case(
                external_case_id,
                path=external_case_store_path,
            )
        )
    except ValueError as exc:
        raise EnterpriseR10BindingCreationError(
            "external_connectivity_case_not_found"
        ) from exc

    try:
        plan = build_enterprise_r10_binding_plan(
            institution_case=institution_case,
            institution_task_id=task_id,
            grant=grant,
            external_connectivity_case=external_case,
            requested_scope_ids=requested_scope_ids,
            connector_scope_ids=connector_scope_ids,
        )

        binding = record_enterprise_r10_binding(
            plan,
            actor=actor,
            path=binding_store_path,
        )
    except (
        EnterpriseR10BindingError,
        EnterpriseR10BindingStoreError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise EnterpriseR10BindingCreationError(
            str(exc)
        ) from exc

    return {
        "status": "validated",
        "binding": binding,
        "credential_issued": False,
        "qualification_key_issued": False,
        "qualification_redeemed": False,
        "sandbox_api_key_issued": False,
        "connector_executed": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }
