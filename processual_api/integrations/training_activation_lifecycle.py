"""Isolated training lifecycle for the existing activation key service.

16G-R3 reuses integration_pilot_controls with explicitly isolated store and
audit files. It does not create a parallel key system, grant a sandbox,
enable runtime, open a network connection, or authorize production.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from processual_api.integrations.training_customer_input_review import (
    TrainingCustomerInputReview,
    TrainingCustomerInputReviewStatus,
)
from processual_api.services import integration_pilot_controls as pilot

__all__ = [
    "TrainingActivationExercise",
    "TrainingActivationIsolation",
    "run_training_activation_lifecycle",
]


_STORE_ENV = "PMK_INTEGRATION_PILOT_TASKS_STORE"
_AUDIT_ENV = "PMK_ADMIN_AUDIT_EVENTS_PATH"


def _resolved_file(name: str, value: Path) -> Path:
    if not isinstance(value, Path):
        raise TypeError(f"{name} must be pathlib.Path.")

    resolved = value.expanduser().resolve()

    if resolved.exists() and resolved.is_dir():
        raise ValueError(f"{name} must be a file path.")

    if not resolved.name:
        raise ValueError(f"{name} must name a file.")

    return resolved


@dataclass(frozen=True, slots=True)
class TrainingActivationIsolation:
    store_path: Path
    audit_path: Path
    training_mode: bool = True

    def __post_init__(self) -> None:
        store = _resolved_file("store_path", self.store_path)
        audit = _resolved_file("audit_path", self.audit_path)

        if self.training_mode is not True:
            raise ValueError("training_mode must remain true.")

        if store == audit:
            raise ValueError("store and audit paths must differ.")

        default_store = pilot._project_root().joinpath(
            "data",
            "integration_pilot_tasks.json",
        ).resolve()
        default_audit = pilot._project_root().joinpath(
            "data",
            "admin_audit_events.jsonl",
        ).resolve()

        if store == default_store:
            raise ValueError("default pilot store is prohibited.")
        if audit == default_audit:
            raise ValueError("default audit path is prohibited.")

        object.__setattr__(self, "store_path", store)
        object.__setattr__(self, "audit_path", audit)


@dataclass(frozen=True, slots=True)
class TrainingActivationExercise:
    task_id: str
    initial_status: str
    key_prefix: str
    raw_key_visible_once: bool
    second_issuance_rejected: bool
    raw_key_absent_from_list: bool
    raw_key_absent_from_store: bool
    raw_key_absent_from_audit: bool
    key_hash_absent_from_public_list: bool
    suspended_status: str
    resumed_status: str
    final_status: str
    final_key_revoked: bool
    sandbox_grant_disabled: bool
    runtime_connector_grant_disabled: bool
    external_http_enabled: bool
    runtime_enabled: bool
    production_allowed: bool

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must not be empty.")
        if not self.key_prefix.startswith("iapk_"):
            raise ValueError("key_prefix must be a masked IAPK reference.")

        for name in (
            "raw_key_visible_once",
            "second_issuance_rejected",
            "raw_key_absent_from_list",
            "raw_key_absent_from_store",
            "raw_key_absent_from_audit",
            "key_hash_absent_from_public_list",
            "final_key_revoked",
            "sandbox_grant_disabled",
            "runtime_connector_grant_disabled",
        ):
            if getattr(self, name) is not True:
                raise ValueError(f"{name} must be true.")

        for name in (
            "external_http_enabled",
            "runtime_enabled",
            "production_allowed",
        ):
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must remain false.")


def _require_accepted_review(
    review: TrainingCustomerInputReview,
) -> None:
    if not isinstance(review, TrainingCustomerInputReview):
        raise TypeError(
            "review must be TrainingCustomerInputReview."
        )

    if review.status is not (
        TrainingCustomerInputReviewStatus.READY_FOR_SUPERVISOR_REVIEW
    ):
        raise ValueError(
            "accepted R2 supervisor-ready review is required."
        )

    if review.ready_for_supervisor_review is not True:
        raise ValueError("R2 review is not supervisor-ready.")

    if review.activation_permission_key_issued is not False:
        raise ValueError("R2 review already reports key issuance.")

    if review.sandbox_launched is not False:
        raise ValueError("R2 review already reports sandbox launch.")

    if review.production_allowed is not False:
        raise ValueError("R2 review must not allow production.")


def _read_text_if_present(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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
def run_training_activation_lifecycle(
    review: TrainingCustomerInputReview,
    isolation: TrainingActivationIsolation,
    *,
    actor: str = "training-supervisor",
) -> TrainingActivationExercise:
    _require_accepted_review(review)

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

    previous_store = os.environ.get(_STORE_ENV)
    previous_audit = os.environ.get(_AUDIT_ENV)

    os.environ[_STORE_ENV] = str(isolation.store_path)
    os.environ[_AUDIT_ENV] = str(isolation.audit_path)

    try:
        created = pilot.create_integration_task(
            {
                "client_id": "training-operator-client",
                "operator_org_id": "training-operator-org",
                "pilot_terms_note": (
                    "Isolated 16G-R3 training lifecycle only."
                ),
                "requested_scopes": (
                    "integration:ticketing:read",
                ),
                "allowed_rate_limits": {
                    "requests_per_minute": 5,
                },
            },
            created_by=actor,
        )

        if created.get("ok") is not True:
            raise RuntimeError("training task creation failed.")

        task = created["task"]
        task_id = str(task["task_id"])
        initial_status = str(task["status"])

        issued = pilot.issue_activation_permission_key(
            task_id,
            {
                "expires_in_minutes": 15,
                "training_reference": (
                    "isolated_16g_r3_training_reference"
                ),
            },
            issued_by=actor,
        )

        if issued.get("ok") is not True:
            raise RuntimeError(
                "training activation permission issuance failed."
            )

        raw_key = str(
            issued.get("activation_permission_key_once") or ""
        )

        if not raw_key.startswith("iapk_"):
            raise RuntimeError(
                "training key did not use the governed prefix."
            )

        raw_visible_once = (
            issued.get(
                "raw_activation_permission_key_visible_once"
            )
            is True
        )

        key_id = raw_key.split(".", maxsplit=1)[0]

        store_before_second = isolation.store_path.read_bytes()
        audit_before_second = isolation.audit_path.read_bytes()

        second = pilot.issue_activation_permission_key(
            task_id,
            {
                "activation_permission_key_id": "",
                "activation_permission_key_hash": "",
                "activation_permission_issued_at": "",
                "status": "pending_supervisor_review",
            },
            issued_by=actor,
        )
        second_rejected = (
            second.get("ok") is False
            and second.get("error")
            == "activation_permission_key_already_issued"
            and "activation_permission_key_once" not in second
        )

        if not second_rejected:
            raise RuntimeError(
                "second training key issuance was not safely rejected."
            )

        if isolation.store_path.read_bytes() != store_before_second:
            raise RuntimeError(
                "second issuance attempt changed the training store."
            )

        if isolation.audit_path.read_bytes() != audit_before_second:
            raise RuntimeError(
                "second issuance attempt changed the training audit."
            )

        listed = pilot.list_integration_tasks()
        listed_text = json.dumps(
            listed,
            ensure_ascii=False,
            sort_keys=True,
        )

        store_text = _read_text_if_present(
            isolation.store_path
        )
        audit_text = _read_text_if_present(
            isolation.audit_path
        )

        raw_absent_list = raw_key not in listed_text
        raw_absent_store = raw_key not in store_text
        raw_absent_audit = raw_key not in audit_text
        hash_absent_list = (
            "activation_permission_key_hash"
            not in listed_text
        )

        suspended = pilot.control_integration_task(
            task_id,
            "suspend",
            actor=actor,
            reason="training suspension proof",
        )
        if suspended.get("ok") is not True:
            raise RuntimeError("training suspension failed.")

        blocked_while_suspended = (
            pilot.issue_activation_permission_key(
                task_id,
                issued_by=actor,
            )
        )
        if blocked_while_suspended.get("ok") is not False:
            raise RuntimeError(
                "suspended task unexpectedly accepted issuance."
            )

        resumed = pilot.control_integration_task(
            task_id,
            "resume",
            actor=actor,
            reason="training resume proof",
        )
        if resumed.get("ok") is not True:
            raise RuntimeError("training resume failed.")

        store_before_resumed_retry = isolation.store_path.read_bytes()
        audit_before_resumed_retry = isolation.audit_path.read_bytes()

        blocked_after_resume = (
            pilot.issue_activation_permission_key(
                task_id,
                issued_by=actor,
            )
        )
        if (
            blocked_after_resume.get("ok") is not False
            or blocked_after_resume.get("error")
            != "activation_permission_key_already_issued"
            or "activation_permission_key_once"
            in blocked_after_resume
        ):
            raise RuntimeError(
                "resumed task unexpectedly accepted reissuance."
            )

        if (
            isolation.store_path.read_bytes()
            != store_before_resumed_retry
        ):
            raise RuntimeError(
                "resumed reissuance changed the training store."
            )

        if (
            isolation.audit_path.read_bytes()
            != audit_before_resumed_retry
        ):
            raise RuntimeError(
                "resumed reissuance changed the training audit."
            )

        revoked = pilot.control_integration_task(
            task_id,
            "revoke",
            actor=actor,
            reason="training revocation proof",
        )
        if revoked.get("ok") is not True:
            raise RuntimeError("training revocation failed.")

        final_task = revoked["task"]

        final_store_text = _read_text_if_present(
            isolation.store_path
        )
        final_audit_text = _read_text_if_present(
            isolation.audit_path
        )

        if raw_key in final_store_text:
            raise RuntimeError("raw training key leaked to store.")
        if raw_key in final_audit_text:
            raise RuntimeError("raw training key leaked to audit.")

        return TrainingActivationExercise(
            task_id=task_id,
            initial_status=initial_status,
            key_prefix=key_id,
            raw_key_visible_once=raw_visible_once,
            second_issuance_rejected=second_rejected,
            raw_key_absent_from_list=raw_absent_list,
            raw_key_absent_from_store=raw_absent_store,
            raw_key_absent_from_audit=raw_absent_audit,
            key_hash_absent_from_public_list=hash_absent_list,
            suspended_status=str(
                suspended["task"]["status"]
            ),
            resumed_status=str(resumed["task"]["status"]),
            final_status=str(final_task["status"]),
            final_key_revoked=(
                final_task["integration_key_revoked"] is True
            ),
            sandbox_grant_disabled=(
                final_task["sandbox_grant_disabled"] is True
            ),
            runtime_connector_grant_disabled=(
                final_task[
                    "runtime_connector_grant_disabled"
                ]
                is True
            ),
            external_http_enabled=False,
            runtime_enabled=False,
            production_allowed=False,
        )
    finally:
        _restore_environment(
            previous_store,
            previous_audit,
        )
