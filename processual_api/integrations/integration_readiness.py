"""Declarative integration readiness checks.

This module evaluates customer-provided readiness inputs against the
credential-readiness profiles introduced in 11D. It does not store secrets,
call external APIs, define customer endpoints, or approve runtime connectors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from processual_api.integrations.credential_profiles import (
    CredentialProfile,
    get_credential_profile,
    list_credential_profiles,
)

ReadinessCheckStatus = Literal[
    "blocked_missing_customer_inputs",
    "blocked_missing_security_controls",
    "ready_for_sandbox_review",
]


@dataclass(frozen=True)
class IntegrationReadinessCheck:
    """Declarative readiness result for one contract/profile pair."""

    readiness_check_id: str
    contract_id: str
    credential_profile_id: str
    required_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    required_security_controls: tuple[str, ...]
    missing_security_controls: tuple[str, ...]
    status: ReadinessCheckStatus
    blocking_reasons: tuple[str, ...]
    next_action: str
    sandbox_ready: bool
    production_allowed: bool
    runtime_connector_approved: bool


def _adapter_contract_ids() -> frozenset[str]:
    from processual_api.integrations import adapter_contracts

    if hasattr(adapter_contracts, "list_adapter_contracts"):
        contracts = adapter_contracts.list_adapter_contracts()
    else:
        registry = getattr(adapter_contracts, "ADAPTER_CONTRACTS", ())
        contracts = registry.values() if isinstance(registry, dict) else registry

    return frozenset(contract.contract_id for contract in contracts)


def _profile_contract_pairs(
    profiles: tuple[CredentialProfile, ...],
) -> tuple[tuple[str, CredentialProfile], ...]:
    pairs: list[tuple[str, CredentialProfile]] = []

    for profile in profiles:
        for contract_id in profile.adapter_contract_ids:
            pairs.append((contract_id, profile))

    return tuple(pairs)


def evaluate_integration_readiness(
    *,
    provided_inputs: set[str] | None = None,
    approved_security_controls: set[str] | None = None,
    credential_profile_ids: set[str] | None = None,
) -> tuple[IntegrationReadinessCheck, ...]:
    """Evaluate declarative readiness without making runtime connections."""

    provided_inputs = provided_inputs or set()
    approved_security_controls = approved_security_controls or set()

    if credential_profile_ids:
        profiles = tuple(
            get_credential_profile(profile_id)
            for profile_id in sorted(credential_profile_ids)
        )
    else:
        profiles = list_credential_profiles()

    checks: list[IntegrationReadinessCheck] = []

    for contract_id, profile in _profile_contract_pairs(profiles):
        required_inputs = tuple(profile.required_customer_inputs)
        missing_inputs = tuple(
            item for item in required_inputs if item not in provided_inputs
        )

        required_security_controls = tuple(profile.required_security_controls)
        missing_security_controls = tuple(
            item
            for item in required_security_controls
            if item not in approved_security_controls
        )

        blocking_reasons: list[str] = []

        if missing_inputs:
            blocking_reasons.append("missing_customer_inputs")

        if missing_security_controls:
            blocking_reasons.append("missing_security_controls")

        if missing_inputs:
            status: ReadinessCheckStatus = "blocked_missing_customer_inputs"
            next_action = "Collect required customer integration inputs."
            sandbox_ready = False
        elif missing_security_controls:
            status = "blocked_missing_security_controls"
            next_action = "Complete required security controls before sandbox review."
            sandbox_ready = False
        else:
            status = "ready_for_sandbox_review"
            next_action = (
                "Proceed to supervised sandbox review; production remains blocked."
            )
            sandbox_ready = True

        checks.append(
            IntegrationReadinessCheck(
                readiness_check_id=(
                    f"{contract_id}:{profile.credential_profile_id}:readiness"
                ),
                contract_id=contract_id,
                credential_profile_id=profile.credential_profile_id,
                required_inputs=required_inputs,
                missing_inputs=missing_inputs,
                required_security_controls=required_security_controls,
                missing_security_controls=missing_security_controls,
                status=status,
                blocking_reasons=tuple(blocking_reasons),
                next_action=next_action,
                sandbox_ready=sandbox_ready,
                production_allowed=False,
                runtime_connector_approved=False,
            )
        )

    return tuple(checks)


def list_integration_readiness_checks() -> tuple[IntegrationReadinessCheck, ...]:
    """Return default blocked readiness checks for all credential profiles."""

    return evaluate_integration_readiness()


def get_integration_readiness_check(
    readiness_check_id: str,
) -> IntegrationReadinessCheck:
    """Return a readiness check by id."""

    for check in list_integration_readiness_checks():
        if check.readiness_check_id == readiness_check_id:
            return check

    raise KeyError(f"Unknown integration readiness check: {readiness_check_id}")


def summarize_integration_readiness(
    checks: tuple[IntegrationReadinessCheck, ...] | None = None,
) -> dict[str, int]:
    """Return a small count summary for admin/client surfaces."""

    checks = checks or list_integration_readiness_checks()

    return {
        "total": len(checks),
        "blocked": sum(1 for check in checks if not check.sandbox_ready),
        "sandbox_ready": sum(1 for check in checks if check.sandbox_ready),
        "production_allowed": sum(1 for check in checks if check.production_allowed),
        "runtime_connector_approved": sum(
            1 for check in checks if check.runtime_connector_approved
        ),
    }


def validate_integration_readiness_checks() -> tuple[str, ...]:
    """Validate readiness-check invariants."""

    issues: list[str] = []
    adapter_contract_ids = _adapter_contract_ids()

    for check in list_integration_readiness_checks():
        if check.contract_id not in adapter_contract_ids:
            issues.append(f"{check.readiness_check_id}: unknown contract")

        if check.production_allowed:
            issues.append(f"{check.readiness_check_id}: production allowed")

        if check.runtime_connector_approved:
            issues.append(f"{check.readiness_check_id}: runtime connector approved")

        if not check.required_inputs:
            issues.append(f"{check.readiness_check_id}: missing required inputs")

        if not check.required_security_controls:
            issues.append(
                f"{check.readiness_check_id}: missing required security controls"
            )

    return tuple(issues)


__all__ = [
    "IntegrationReadinessCheck",
    "ReadinessCheckStatus",
    "evaluate_integration_readiness",
    "get_integration_readiness_check",
    "list_integration_readiness_checks",
    "summarize_integration_readiness",
    "validate_integration_readiness_checks",
]
