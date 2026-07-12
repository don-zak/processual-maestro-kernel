"""Reference-only outbound allowlist and TLS simulation for 16G-R5.

This module evaluates accepted R2 network-policy references through the
existing 16F-R3A readiness assessment. It never resolves DNS, opens a port or
socket, creates a TLS context, loads certificates, configures a proxy,
authorizes egress, arms a kill switch, performs HTTP, launches a sandbox,
enables runtime, or authorizes production.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from processual_api.integrations.outbound_allowlist_tls_readiness import (
    OutboundAllowlistTlsReadinessStatus,
    OutboundAllowlistTlsReferenceSubmission,
    TlsMinimumVersion,
    assess_outbound_allowlist_tls_readiness,
)
from processual_api.integrations.training_activation_lifecycle import (
    TrainingActivationIsolation,
)
from processual_api.integrations.training_customer_input_review import (
    TrainingCustomerInputReview,
    TrainingCustomerInputReviewStatus,
    TrainingCustomerInputSubmission,
    review_training_customer_input_submission,
)
from processual_api.services import integration_pilot_controls as pilot

__all__ = [
    "TrainingOutboundTlsApprovalSimulation",
    "simulate_training_outbound_tls_approval",
]


_READINESS_ID = (
    "telecom_ticketing_outbound_allowlist_tls_readiness"
)
_STORE_ENV = "PMK_INTEGRATION_PILOT_TASKS_STORE"
_AUDIT_ENV = "PMK_ADMIN_AUDIT_EVENTS_PATH"


@dataclass(frozen=True, slots=True)
class TrainingOutboundTlsApprovalSimulation:
    task_id: str
    activation_permission_key_id: str
    connector_id: str
    selected_tls_minimum_version: str
    assessment_status: str
    reference_count: int
    required_reference_count: int
    activation_permission_key_validated: bool
    ready_for_network_policy_review: bool
    approval_simulation_created: bool
    final_status: str
    final_key_revoked: bool
    allowlist_applied: bool
    dns_resolution_performed: bool
    port_opened: bool
    tls_context_created: bool
    ca_bundle_loaded: bool
    certificate_loaded: bool
    certificate_pin_applied: bool
    proxy_configured: bool
    egress_authorized: bool
    kill_switch_armed: bool
    connection_attempted: bool
    external_http_enabled: bool
    socket_access_enabled: bool
    persistence_allowed: bool
    background_task_allowed: bool
    route_exposure_allowed: bool
    runtime_enabled: bool
    production_allowed: bool
    automatic_activation_allowed: bool

    def __post_init__(self) -> None:
        if not self.task_id.startswith("itask_"):
            raise ValueError("task_id must be a training task reference.")
        if not self.activation_permission_key_id.startswith("iapk_"):
            raise ValueError(
                "activation_permission_key_id must be a safe key id."
            )
        if self.connector_id != "telecom_ticketing_reference":
            raise ValueError("connector_id must remain the ticketing reference.")
        if self.selected_tls_minimum_version not in {
            TlsMinimumVersion.TLS_1_2.value,
            TlsMinimumVersion.TLS_1_3.value,
        }:
            raise ValueError("unsupported TLS minimum version.")
        if self.assessment_status != (
            OutboundAllowlistTlsReadinessStatus
            .REFERENCES_RECEIVED_FOR_REVIEW.value
        ):
            raise ValueError(
                "assessment must be received for network-policy review."
            )
        if self.reference_count != 11:
            raise ValueError("reference_count must be eleven.")
        if self.required_reference_count != 11:
            raise ValueError(
                "required_reference_count must be eleven."
            )
        if self.final_status != "revoked":
            raise ValueError("final_status must be revoked.")

        for name in (
            "activation_permission_key_validated",
            "ready_for_network_policy_review",
            "approval_simulation_created",
            "final_key_revoked",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must be true.")

        for name in (
            "allowlist_applied",
            "dns_resolution_performed",
            "port_opened",
            "tls_context_created",
            "ca_bundle_loaded",
            "certificate_loaded",
            "certificate_pin_applied",
            "proxy_configured",
            "egress_authorized",
            "kill_switch_armed",
            "connection_attempted",
            "external_http_enabled",
            "socket_access_enabled",
            "persistence_allowed",
            "background_task_allowed",
            "route_exposure_allowed",
            "runtime_enabled",
            "production_allowed",
            "automatic_activation_allowed",
        ):
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


def _require_matching_ready_review(
    review: TrainingCustomerInputReview,
    submission: TrainingCustomerInputSubmission,
) -> None:
    if not isinstance(review, TrainingCustomerInputReview):
        raise TypeError(
            "review must be TrainingCustomerInputReview."
        )
    if not isinstance(submission, TrainingCustomerInputSubmission):
        raise TypeError(
            "submission must be TrainingCustomerInputSubmission."
        )
    if review.status is not (
        TrainingCustomerInputReviewStatus.READY_FOR_SUPERVISOR_REVIEW
    ):
        raise ValueError(
            "accepted R2 supervisor-ready review is required."
        )
    if review.ready_for_supervisor_review is not True:
        raise ValueError("R2 review is not supervisor-ready.")
    if review.submission_id != submission.submission_id:
        raise ValueError("review and submission identifiers differ.")
    if review.request_id != submission.request_id:
        raise ValueError("review and request identifiers differ.")

    canonical = review_training_customer_input_submission(submission)
    if canonical != review:
        raise ValueError(
            "review does not match the canonical R2 submission review."
        )


def _outbound_submission(
    submission: TrainingCustomerInputSubmission,
) -> OutboundAllowlistTlsReferenceSubmission:
    values = submission.values

    try:
        tls_version = TlsMinimumVersion(
            values["outbound.tls_minimum_version_selection"]
        )
        return OutboundAllowlistTlsReferenceSubmission(
            submission_id=f"{submission.submission_id}_outbound_tls",
            readiness_id=_READINESS_ID,
            tls_minimum_version=tls_version,
            allowlist_reference=values[
                "outbound.allowlist_reference"
            ],
            host_reference=values["outbound.host_reference"],
            dns_policy_reference=values[
                "outbound.dns_policy_reference"
            ],
            port_policy_reference=values[
                "outbound.port_policy_reference"
            ],
            ca_policy_reference=values[
                "outbound.ca_policy_reference"
            ],
            certificate_pinning_policy_reference=values[
                "outbound.certificate_pinning_policy_reference"
            ],
            proxy_policy_reference=values[
                "outbound.proxy_policy_reference"
            ],
            egress_authorization_reference=values[
                "outbound.egress_authorization_reference"
            ],
            security_review_reference=values[
                "outbound.security_review_reference"
            ],
            operator_approval_reference=values[
                "outbound.operator_approval_reference"
            ],
            kill_switch_reference=values[
                "outbound.kill_switch_reference"
            ],
        )
    except KeyError as exc:
        raise ValueError(
            f"missing outbound reference: {exc.args[0]}"
        ) from exc


def _restore_environment(
    previous_store: str | None,
    previous_audit: str | None,
) -> None:
    if previous_store is None:
        os.environ.pop(_STORE_ENV, None)
    else:
        os.environ[_STORE_ENV] = previous_store

    if previous_audit is None:
        os.environ.pop(_AUDIT_ENV, None)
    else:
        os.environ[_AUDIT_ENV] = previous_audit


def _read_text_if_present(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def simulate_training_outbound_tls_approval(
    review: TrainingCustomerInputReview,
    submission: TrainingCustomerInputSubmission,
    isolation: TrainingActivationIsolation,
    *,
    actor: str = "training-supervisor",
) -> TrainingOutboundTlsApprovalSimulation:
    _require_matching_ready_review(review, submission)

    if not isinstance(isolation, TrainingActivationIsolation):
        raise TypeError(
            "isolation must be TrainingActivationIsolation."
        )
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor must be a non-empty string.")
    if isolation.store_path.exists():
        raise ValueError(
            "isolated training store must not already exist."
        )
    if isolation.audit_path.exists():
        raise ValueError(
            "isolated training audit must not already exist."
        )

    outbound_submission = _outbound_submission(submission)

    previous_store = os.environ.get(_STORE_ENV)
    previous_audit = os.environ.get(_AUDIT_ENV)
    os.environ[_STORE_ENV] = str(isolation.store_path)
    os.environ[_AUDIT_ENV] = str(isolation.audit_path)

    task_id = ""
    raw_key = ""
    revoked = False

    try:
        created = pilot.create_integration_task(
            {
                "client_id": "training-outbound-tls-client",
                "operator_org_id": "training-outbound-tls-operator",
                "pilot_terms_note": (
                    "Isolated 16G-R5 reference-only simulation."
                ),
                "allowed_operations": (
                    "review_operator_inputs",
                ),
            },
            created_by=actor,
        )
        if created.get("ok") is not True:
            raise RuntimeError("R5 training task creation failed.")

        task_id = str(created["task"]["task_id"])

        issued = pilot.issue_activation_permission_key(
            task_id,
            issued_by=actor,
        )
        if issued.get("ok") is not True:
            raise RuntimeError(
                "R5 activation permission issuance failed."
            )

        raw_key = str(
            issued.get("activation_permission_key_once") or ""
        )
        key_id = str(
            issued["task"]["activation_permission_key_id"]
        )

        validated = pilot.validate_activation_permission_key(
            task_id,
            raw_key,
        )
        if (
            validated.get("ok") is not True
            or validated.get(
                "activation_permission_key_valid"
            )
            is not True
        ):
            raise RuntimeError(
                "R5 activation permission validation failed."
            )

        assessment = assess_outbound_allowlist_tls_readiness(
            _READINESS_ID,
            outbound_submission,
        )
        if (
            assessment.status is not (
                OutboundAllowlistTlsReadinessStatus
                .REFERENCES_RECEIVED_FOR_REVIEW
            )
            or assessment.ready_for_network_policy_review is not True
        ):
            raise RuntimeError(
                "R5 network-policy references were not review-ready."
            )

        revoked_result = pilot.control_integration_task(
            task_id,
            "revoke",
            actor=actor,
            reason="R5 simulation completed and revoked.",
        )
        if revoked_result.get("ok") is not True:
            raise RuntimeError("R5 training revocation failed.")
        revoked = True
        final_task = revoked_result["task"]

        store_text = _read_text_if_present(isolation.store_path)
        audit_text = _read_text_if_present(isolation.audit_path)

        if raw_key in store_text or raw_key in audit_text:
            raise RuntimeError(
                "raw activation permission key leaked."
            )

        safe_metadata = json.dumps(
            {
                "task_id": task_id,
                "key_id": key_id,
                "connector_id": assessment.connector_id,
                "tls": (
                    assessment
                    .selected_tls_minimum_version_reference
                ),
                "reference_count": assessment.reference_count,
            },
            sort_keys=True,
        )
        if raw_key in safe_metadata:
            raise RuntimeError(
                "raw key leaked into R5 simulation metadata."
            )

        return TrainingOutboundTlsApprovalSimulation(
            task_id=task_id,
            activation_permission_key_id=key_id,
            connector_id=assessment.connector_id,
            selected_tls_minimum_version=(
                assessment
                .selected_tls_minimum_version_reference
            ),
            assessment_status=assessment.status.value,
            reference_count=assessment.reference_count,
            required_reference_count=(
                assessment.required_reference_count
            ),
            activation_permission_key_validated=True,
            ready_for_network_policy_review=(
                assessment.ready_for_network_policy_review
            ),
            approval_simulation_created=True,
            final_status=str(final_task["status"]),
            final_key_revoked=(
                final_task["integration_key_revoked"] is True
            ),
            allowlist_applied=assessment.allowlist_applied,
            dns_resolution_performed=(
                assessment.dns_resolution_performed
            ),
            port_opened=assessment.port_opened,
            tls_context_created=assessment.tls_context_created,
            ca_bundle_loaded=assessment.ca_bundle_loaded,
            certificate_loaded=assessment.certificate_loaded,
            certificate_pin_applied=(
                assessment.certificate_pin_applied
            ),
            proxy_configured=assessment.proxy_configured,
            egress_authorized=assessment.egress_authorized,
            kill_switch_armed=assessment.kill_switch_armed,
            connection_attempted=assessment.connection_attempted,
            external_http_enabled=(
                assessment.external_http_enabled
            ),
            socket_access_enabled=(
                assessment.socket_access_enabled
            ),
            persistence_allowed=assessment.persistence_allowed,
            background_task_allowed=(
                assessment.background_task_allowed
            ),
            route_exposure_allowed=(
                assessment.route_exposure_allowed
            ),
            runtime_enabled=assessment.runtime_enabled,
            production_allowed=assessment.production_allowed,
            automatic_activation_allowed=(
                assessment.automatic_activation_allowed
            ),
        )
    finally:
        if task_id and not revoked:
            pilot.control_integration_task(
                task_id,
                "revoke",
                actor=actor,
                reason="R5 simulation aborted and revoked.",
            )

        raw_key = ""
        _restore_environment(previous_store, previous_audit)
