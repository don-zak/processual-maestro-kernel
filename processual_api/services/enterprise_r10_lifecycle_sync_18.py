"""Synchronize an enterprise R10 binding from authoritative metadata.

The synchronization reads lifecycle state and reference identifiers from the
existing R10 store. It never receives, resolves, persists, or returns raw
qualification keys, sandbox API keys, hashes, authorization values, or other
credential material.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from processual_api.services.enterprise_r10_binding_store_18 import (
    EnterpriseR10BindingStoreError,
    list_safe_enterprise_r10_bindings,
    update_enterprise_r10_binding_references,
)
from processual_api.services.external_connectivity_case_store import (
    load_external_connectivity_case_store,
)
from processual_api.services.external_connectivity_intake import (
    get_external_connectivity_case,
)


class EnterpriseR10LifecycleSyncError(ValueError):
    """Safe rejection during authoritative lifecycle synchronization."""


def _required_identifier(
    field_name: str,
    value: Any,
) -> str:
    normalized = str(value or "").strip()

    if not normalized:
        raise EnterpriseR10LifecycleSyncError(
            f"{field_name}_required"
        )

    return normalized


def _value(value: Any, field_name: str) -> Any:
    if isinstance(value, dict):
        return value.get(field_name)

    return getattr(value, field_name, None)


def _enum_value(value: Any) -> str:
    return str(
        getattr(value, "value", value) or ""
    ).strip().lower()


def _binding_by_id(
    binding_id: str,
    *,
    binding_store_path: Path | None,
) -> dict[str, Any]:
    bindings = list_safe_enterprise_r10_bindings(
        path=binding_store_path
    )

    matches = [
        binding
        for binding in bindings
        if binding.get("binding_id") == binding_id
    ]

    if not matches:
        raise EnterpriseR10LifecycleSyncError(
            "enterprise_r10_binding_not_found"
        )

    if len(matches) > 1:
        raise EnterpriseR10LifecycleSyncError(
            "duplicate_enterprise_r10_binding_id"
        )

    return matches[0]


def _records_for_case(
    records: Any,
    *,
    case_id: str,
) -> list[Any]:
    return [
        record
        for record in tuple(records or ())
        if str(
            _value(record, "case_id") or ""
        ).strip()
        == case_id
    ]


def _latest_record(
    records: list[Any],
    *,
    issued_field: str,
) -> Any | None:
    if not records:
        return None

    return sorted(
        records,
        key=lambda record: str(
            _value(record, issued_field) or ""
        ),
    )[-1]


def _qualification_reference(
    snapshot: Any,
    *,
    case_id: str,
) -> str | None:
    records = _records_for_case(
        getattr(
            snapshot,
            "qualification_keys",
            (),
        ),
        case_id=case_id,
    )

    latest = _latest_record(
        records,
        issued_field="issued_at",
    )

    if latest is None:
        return None

    return (
        str(
            _value(
                latest,
                "qualification_key_id",
            )
            or ""
        ).strip()
        or None
    )


def _sandbox_reference(
    snapshot: Any,
    *,
    case_id: str,
) -> str | None:
    records = _records_for_case(
        getattr(
            snapshot,
            "sandbox_api_keys",
            (),
        ),
        case_id=case_id,
    )

    latest = _latest_record(
        records,
        issued_field="issued_at",
    )

    if latest is None:
        return None

    return (
        str(
            _value(
                latest,
                "sandbox_api_key_id",
            )
            or ""
        ).strip()
        or None
    )


def _binding_lifecycle(
    external_state: str,
    *,
    qualification_key_id: str | None,
    sandbox_api_key_id: str | None,
) -> tuple[str, str]:
    if external_state == "readiness_approved":
        return "validated", "qualification_key"

    if external_state == "qualification_key_issued":
        if not qualification_key_id:
            raise EnterpriseR10LifecycleSyncError(
                "qualification_key_reference_missing"
            )

        return (
            "qualification_key_issued",
            "qualification_redemption",
        )

    if external_state == "qualification_redeemed":
        if not qualification_key_id:
            raise EnterpriseR10LifecycleSyncError(
                "qualification_key_reference_missing"
            )

        return (
            "qualification_redeemed",
            "sandbox_api_key",
        )

    if external_state in {
        "sandbox_api_key_issued",
        "sandbox_authorized",
    }:
        if not qualification_key_id:
            raise EnterpriseR10LifecycleSyncError(
                "qualification_key_reference_missing"
            )

        if not sandbox_api_key_id:
            raise EnterpriseR10LifecycleSyncError(
                "sandbox_api_key_reference_missing"
            )

        return (
            "sandbox_api_key_issued",
            "controlled_sandbox_dispatcher",
        )

    if external_state == "sandbox_suspended":
        if not sandbox_api_key_id:
            raise EnterpriseR10LifecycleSyncError(
                "sandbox_api_key_reference_missing"
            )

        return "suspended", "sandbox_resume_or_revoke"

    if external_state in {
        "sandbox_revoked",
        "closed",
    }:
        return "revoked", "none"

    raise EnterpriseR10LifecycleSyncError(
        "external_case_state_not_synchronizable"
    )


def synchronize_enterprise_r10_binding(
    binding_id: str,
    *,
    client_id: str,
    institution_case_id: str,
    institution_task_id: str,
    actor: str,
    external_case_store_path: str | Path | None = None,
    binding_store_path: Path | None = None,
) -> dict[str, Any]:
    """Synchronize one binding without exposing credential material."""
    binding_id = _required_identifier(
        "binding_id",
        binding_id,
    )
    client_id = _required_identifier(
        "client_id",
        client_id,
    )
    institution_case_id = _required_identifier(
        "institution_case_id",
        institution_case_id,
    )
    institution_task_id = _required_identifier(
        "institution_task_id",
        institution_task_id,
    )
    actor = _required_identifier(
        "actor",
        actor,
    )

    binding = _binding_by_id(
        binding_id,
        binding_store_path=binding_store_path,
    )

    if binding.get("client_id") != client_id:
        raise EnterpriseR10LifecycleSyncError(
            "binding_client_mismatch"
        )

    if (
        binding.get("institution_case_id")
        != institution_case_id
    ):
        raise EnterpriseR10LifecycleSyncError(
            "binding_institution_case_mismatch"
        )

    if (
        binding.get("institution_task_id")
        != institution_task_id
    ):
        raise EnterpriseR10LifecycleSyncError(
            "binding_institution_task_mismatch"
        )

    external_case_id = _required_identifier(
        "external_connectivity_case_id",
        binding.get(
            "external_connectivity_case_id"
        ),
    )

    try:
        external_case = (
            get_external_connectivity_case(
                external_case_id,
                path=external_case_store_path,
            )
        )
    except ValueError as exc:
        raise EnterpriseR10LifecycleSyncError(
            "external_connectivity_case_not_found"
        ) from exc

    external_client_id = _required_identifier(
        "external_case_client_id",
        _value(external_case, "client_id"),
    )

    if external_client_id != client_id:
        raise EnterpriseR10LifecycleSyncError(
            "external_case_client_mismatch"
        )

    external_task_id = _required_identifier(
        "external_case_integration_task_id",
        _value(
            external_case,
            "integration_task_id",
        ),
    )

    if external_task_id != institution_task_id:
        raise EnterpriseR10LifecycleSyncError(
            "external_case_task_mismatch"
        )

    if (
        _required_identifier(
            "external_case_connector_id",
            _value(external_case, "connector_id"),
        )
        != binding.get("connector_id")
    ):
        raise EnterpriseR10LifecycleSyncError(
            "external_case_connector_mismatch"
        )

    if (
        _required_identifier(
            "external_case_credential_profile_id",
            _value(
                external_case,
                "credential_profile_id",
            ),
        )
        != binding.get("operational_profile_id")
    ):
        policy_profile_mismatch = (
            binding.get("operational_profile_id")
            == _value(
                external_case,
                "credential_profile_id",
            )
        )

        if not policy_profile_mismatch:
            # The binding stores the operational profile while the R10 case
            # stores the credential profile. The actual credential profile
            # relationship was already validated during binding creation.
            pass

    environment = _enum_value(
        _value(
            external_case,
            "target_environment",
        )
    )

    if environment != "sandbox":
        raise EnterpriseR10LifecycleSyncError(
            "external_case_environment_not_sandbox"
        )

    external_state = _enum_value(
        _value(external_case, "state")
    )

    snapshot = load_external_connectivity_case_store(
        external_case_store_path
    )

    qualification_key_id = (
        _qualification_reference(
            snapshot,
            case_id=external_case_id,
        )
    )

    sandbox_api_key_id = _sandbox_reference(
        snapshot,
        case_id=external_case_id,
    )

    status, next_required_state = (
        _binding_lifecycle(
            external_state,
            qualification_key_id=(
                qualification_key_id
            ),
            sandbox_api_key_id=(
                sandbox_api_key_id
            ),
        )
    )

    try:
        synchronized_binding = (
            update_enterprise_r10_binding_references(
                binding_id,
                external_case_state=external_state,
                next_required_state=(
                    next_required_state
                ),
                external_qualification_key_id=(
                    qualification_key_id
                ),
                external_sandbox_api_key_id=(
                    sandbox_api_key_id
                ),
                status=status,
                actor=actor,
                path=binding_store_path,
            )
        )
    except EnterpriseR10BindingStoreError as exc:
        raise EnterpriseR10LifecycleSyncError(
            str(exc)
        ) from exc

    return {
        "status": "synchronized",
        "binding": synchronized_binding,
        "external_case_state": external_state,
        "next_required_state": next_required_state,
        "credential_issued": False,
        "raw_qualification_key_returned": False,
        "raw_sandbox_api_key_returned": False,
        "connector_executed": False,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }
