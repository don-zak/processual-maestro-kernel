"""Reference-only secret-provider binding simulation for 16G-R4.

The simulation reuses R2 customer references, the 16F-R2A readiness
assessment, and the existing pilot task/key service. It never initializes a
provider client, resolves or stores a secret, authenticates, opens a network
connection, launches a sandbox, enables runtime, or authorizes production.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from processual_api.integrations.secret_provider_binding_readiness import (
    SecretProviderBindingReadinessStatus,
    SecretProviderKind,
    SecretProviderReferenceSubmission,
    assess_secret_provider_binding_readiness,
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
    "TrainingSecretProviderBindingSimulation",
    "simulate_training_secret_provider_binding",
]


_READINESS_ID = (
    "telecom_ticketing_secret_provider_binding_readiness"
)
_STORE_ENV = "PMK_INTEGRATION_PILOT_TASKS_STORE"
_AUDIT_ENV = "PMK_ADMIN_AUDIT_EVENTS_PATH"


@dataclass(frozen=True, slots=True)
class TrainingSecretProviderBindingSimulation:
    task_id: str
    activation_permission_key_id: str
    selected_provider: str
    assessment_status: str
    reference_count: int
    required_reference_count: int
    activation_permission_key_validated: bool
    ready_for_provider_review: bool
    binding_simulation_created: bool
    final_status: str
    final_key_revoked: bool
    provider_binding_created: bool
    provider_client_initialized: bool
    secret_reference_registered: bool
    secret_value_accessed: bool
    secret_value_stored: bool
    raw_secret_visible: bool
    authentication_performed: bool
    credentials_resolved: bool
    resolution_allowed: bool
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
        if not self.selected_provider:
            raise ValueError("selected_provider must not be empty.")
        if self.assessment_status != (
            SecretProviderBindingReadinessStatus
            .REFERENCES_RECEIVED_FOR_REVIEW.value
        ):
            raise ValueError(
                "assessment must be received for provider review."
            )
        if self.reference_count != 7:
            raise ValueError("reference_count must be seven.")
        if self.required_reference_count != 7:
            raise ValueError(
                "required_reference_count must be seven."
            )

        for name in (
            "activation_permission_key_validated",
            "ready_for_provider_review",
            "binding_simulation_created",
            "final_key_revoked",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must be true.")

        if self.final_status != "revoked":
            raise ValueError("final_status must be revoked.")

        for name in (
            "provider_binding_created",
            "provider_client_initialized",
            "secret_reference_registered",
            "secret_value_accessed",
            "secret_value_stored",
            "raw_secret_visible",
            "authentication_performed",
            "credentials_resolved",
            "resolution_allowed",
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

    canonical_review = review_training_customer_input_submission(
        submission
    )
    if canonical_review != review:
        raise ValueError(
            "review does not match the canonical R2 submission review."
        )


def _provider_submission(
    submission: TrainingCustomerInputSubmission,
) -> SecretProviderReferenceSubmission:
    values = submission.values

    try:
        provider_kind = SecretProviderKind(
            values["provider.selected_secret_provider"]
        )
        return SecretProviderReferenceSubmission(
            submission_id=(
                f"{submission.submission_id}_provider_binding"
            ),
            readiness_id=_READINESS_ID,
            provider_kind=provider_kind,
            provider_reference=values[
                "provider.provider_reference"
            ],
            authentication_reference=values[
                "provider.authentication_method_reference"
            ],
            rotation_policy_reference=values[
                "provider.rotation_policy_reference"
            ],
            customer_authorization_reference=values[
                "provider.customer_authorization_reference"
            ],
            operator_approval_reference=values[
                "provider.operator_approval_reference"
            ],
            security_review_reference=values[
                "provider.security_review_reference"
            ],
            revocation_policy_reference=values[
                "provider.revocation_policy_reference"
            ],
        )
    except KeyError as exc:
        raise ValueError(
            f"missing provider reference: {exc.args[0]}"
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


def _read_text_if_present(path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def simulate_training_secret_provider_binding(
    review: TrainingCustomerInputReview,
    submission: TrainingCustomerInputSubmission,
    isolation: TrainingActivationIsolation,
    *,
    actor: str = "training-supervisor",
) -> TrainingSecretProviderBindingSimulation:
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

    provider_submission = _provider_submission(submission)

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
                "client_id": "training-provider-binding-client",
                "operator_org_id": (
                    "training-provider-binding-operator"
                ),
                "pilot_terms_note": (
                    "Isolated 16G-R4 reference-only simulation."
                ),
                "allowed_operations": (
                    "review_operator_inputs",
                ),
            },
            created_by=actor,
        )
        if created.get("ok") is not True:
            raise RuntimeError("R4 training task creation failed.")

        task_id = str(created["task"]["task_id"])

        issued = pilot.issue_activation_permission_key(
            task_id,
            issued_by=actor,
        )
        if issued.get("ok") is not True:
            raise RuntimeError(
                "R4 activation permission issuance failed."
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
                "R4 activation permission validation failed."
            )

        assessment = assess_secret_provider_binding_readiness(
            _READINESS_ID,
            provider_submission,
        )
        if (
            assessment.status is not (
                SecretProviderBindingReadinessStatus
                .REFERENCES_RECEIVED_FOR_REVIEW
            )
            or assessment.ready_for_provider_review is not True
        ):
            raise RuntimeError(
                "R4 provider references were not review-ready."
            )

        revoked_result = pilot.control_integration_task(
            task_id,
            "revoke",
            actor=actor,
            reason="R4 simulation completed and revoked.",
        )
        if revoked_result.get("ok") is not True:
            raise RuntimeError("R4 training revocation failed.")
        revoked = True
        final_task = revoked_result["task"]

        store_text = _read_text_if_present(
            isolation.store_path
        )
        audit_text = _read_text_if_present(
            isolation.audit_path
        )

        if raw_key in store_text or raw_key in audit_text:
            raise RuntimeError(
                "raw activation permission key leaked."
            )

        serialized_assessment = json.dumps(
            {
                "task_id": task_id,
                "key_id": key_id,
                "provider": (
                    assessment.selected_provider_reference
                ),
                "reference_count": assessment.reference_count,
            },
            sort_keys=True,
        )
        if raw_key in serialized_assessment:
            raise RuntimeError(
                "raw key leaked into simulation metadata."
            )

        return TrainingSecretProviderBindingSimulation(
            task_id=task_id,
            activation_permission_key_id=key_id,
            selected_provider=(
                assessment.selected_provider_reference
            ),
            assessment_status=assessment.status.value,
            reference_count=assessment.reference_count,
            required_reference_count=(
                assessment.required_reference_count
            ),
            activation_permission_key_validated=True,
            ready_for_provider_review=(
                assessment.ready_for_provider_review
            ),
            binding_simulation_created=True,
            final_status=str(final_task["status"]),
            final_key_revoked=(
                final_task["integration_key_revoked"] is True
            ),
            provider_binding_created=(
                assessment.provider_binding_created
            ),
            provider_client_initialized=(
                assessment.provider_client_initialized
            ),
            secret_reference_registered=(
                assessment.secret_reference_registered
            ),
            secret_value_accessed=(
                assessment.secret_value_accessed
            ),
            secret_value_stored=assessment.secret_value_stored,
            raw_secret_visible=assessment.raw_secret_visible,
            authentication_performed=(
                assessment.authentication_performed
            ),
            credentials_resolved=(
                assessment.credentials_resolved
            ),
            resolution_allowed=assessment.resolution_allowed,
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
                reason="R4 simulation aborted and revoked.",
            )

        raw_key = ""
        _restore_environment(
            previous_store,
            previous_audit,
        )
