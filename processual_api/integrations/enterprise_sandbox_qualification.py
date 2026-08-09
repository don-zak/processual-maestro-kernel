"""Customer-specific Enterprise sandbox qualification without runtime activation.

The qualification contract stores and evaluates identifiers only. It never accepts
credential values, secret material, endpoint URLs, or client-asserted security
approvals. Customer-provided input presence can advance qualification to the
supervised security-review boundary, but runtime and production remain blocked.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from processual_api.integrations.credential_profiles import get_credential_profile
from processual_api.integrations.integration_readiness import (
    evaluate_integration_readiness,
    summarize_integration_readiness,
)
from processual_api.integrations.scope_catalog import get_integration_scope


def _unique_ids(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = {str(value).strip().lower() for value in values if str(value).strip()}
    return tuple(sorted(normalized))


def build_customer_sandbox_qualification(
    *,
    credential_profile_id: str,
    requested_scope_ids: list[str] | tuple[str, ...],
    provided_input_ids: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Build a safe, client-specific sandbox qualification snapshot.

    Only known catalog/profile identifiers are accepted. Security-control approval
    is deliberately not an input to this function: that boundary is supervised.
    """

    normalized_profile_id = str(credential_profile_id or "").strip().lower()
    if not normalized_profile_id:
        raise ValueError("credential_profile_id is required")

    profile = get_credential_profile(normalized_profile_id)
    scope_ids = _unique_ids(requested_scope_ids)
    if not scope_ids:
        raise ValueError("at least one requested scope is required")

    scopes = []
    for scope_id in scope_ids:
        try:
            scopes.append(get_integration_scope(scope_id))
        except KeyError as exc:
            raise ValueError(f"unsupported integration scope: {scope_id}") from exc

    provided_inputs = _unique_ids(provided_input_ids)
    required_inputs = tuple(profile.required_customer_inputs)
    unknown_inputs = sorted(set(provided_inputs) - set(required_inputs))
    if unknown_inputs:
        raise ValueError(
            "unsupported customer input identifiers: " + ", ".join(unknown_inputs)
        )

    checks = evaluate_integration_readiness(
        provided_inputs=set(provided_inputs),
        approved_security_controls=set(),
        credential_profile_ids={profile.credential_profile_id},
    )
    readiness = summarize_integration_readiness(checks)
    by_access = Counter(scope.access_level for scope in scopes)
    supervisor_scope_count = sum(
        1 for scope in scopes if scope.requires_supervisor_approval
    )
    missing_input_ids = tuple(
        item for item in required_inputs if item not in set(provided_inputs)
    )

    return {
        "configured": True,
        "credential_profile_id": profile.credential_profile_id,
        "requested_scope_ids": list(scope_ids),
        "provided_input_ids": list(provided_inputs),
        "missing_input_ids": list(missing_input_ids),
        "required_security_control_ids": list(profile.required_security_controls),
        "security_controls_approved": 0,
        "scope_posture": {
            "source": "catalog",
            "total": len(scopes),
            "read": by_access.get("read", 0),
            "write": by_access.get("write", 0),
            "restricted": by_access.get("restricted", 0),
            "supervisor_approval_required": supervisor_scope_count,
            "read_only_pilot_eligible": bool(scopes)
            and all(scope.allowed_in_read_only_pilot for scope in scopes),
        },
        "readiness": readiness,
        "readiness_checks": [
            {
                "readiness_check_id": check.readiness_check_id,
                "contract_id": check.contract_id,
                "credential_profile_id": check.credential_profile_id,
                "status": check.status,
                "missing_inputs": list(check.missing_inputs),
                "missing_security_controls": list(check.missing_security_controls),
                "blocking_reasons": list(check.blocking_reasons),
                "next_action": check.next_action,
                "sandbox_ready": check.sandbox_ready,
                "production_allowed": False,
                "runtime_connector_approved": False,
            }
            for check in checks
        ],
        "sandbox_ready": bool(checks) and all(check.sandbox_ready for check in checks),
        "production_allowed": False,
        "runtime_connector_approved": False,
        "next_action": (
            "Complete the remaining declared customer inputs."
            if missing_input_ids
            else "Submit required security controls for supervised review."
        ),
    }


__all__ = ["build_customer_sandbox_qualification"]
