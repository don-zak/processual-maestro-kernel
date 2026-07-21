"""Safe Stage 18 metadata store for enterprise-to-R10 bindings.

The store records identifiers, lifecycle states, and audit metadata only.
It must never store raw keys, hashes, authorization headers, session values,
provider secrets, or credential material.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

ENTERPRISE_R10_BINDING_STORE_VERSION = 1

FORBIDDEN_BINDING_STORE_KEYS = {
    "api_key",
    "sandbox_api_key",
    "qualification_key",
    "raw_key",
    "raw_value",
    "key_hash",
    "hashed_key",
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "provider_secret",
    "supervisor_session_key",
}


class EnterpriseR10BindingStoreError(ValueError):
    """Safe binding-store validation error."""


def enterprise_r10_binding_store_path() -> Path:
    configured = os.environ.get(
        "PMK_ENTERPRISE_R10_BINDING_STORE_PATH",
        "",
    ).strip()

    if configured:
        return Path(configured)

    return (
        Path(__file__).resolve().parents[1]
        / "data"
        / "enterprise_r10_bindings_18.json"
    )


def empty_enterprise_r10_binding_store() -> dict[str, Any]:
    return {
        "version": ENTERPRISE_R10_BINDING_STORE_VERSION,
        "bindings": [],
        "audit": [],
    }


def _validate_secret_free(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).strip().lower()

            if normalized_key in FORBIDDEN_BINDING_STORE_KEYS:
                raise EnterpriseR10BindingStoreError(
                    "Credential material is forbidden "
                    "in the enterprise R10 binding store."
                )

            _validate_secret_free(child)

        return

    if isinstance(value, list | tuple):
        for child in value:
            _validate_secret_free(child)


def load_enterprise_r10_binding_store(
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or enterprise_r10_binding_store_path()

    if not target.exists():
        return empty_enterprise_r10_binding_store()

    try:
        raw = json.loads(
            target.read_text(encoding="utf-8")
        )
    except (
        json.JSONDecodeError,
        OSError,
        UnicodeError,
    ) as exc:
        raise EnterpriseR10BindingStoreError(
            "Enterprise R10 binding store is unreadable."
        ) from exc

    if not isinstance(raw, dict):
        raise EnterpriseR10BindingStoreError(
            "Enterprise R10 binding store must be an object."
        )

    if (
        raw.get("version")
        != ENTERPRISE_R10_BINDING_STORE_VERSION
    ):
        raise EnterpriseR10BindingStoreError(
            "Unsupported enterprise R10 binding store version."
        )

    if not isinstance(raw.get("bindings"), list):
        raise EnterpriseR10BindingStoreError(
            "Binding store bindings must be a list."
        )

    if not isinstance(raw.get("audit"), list):
        raise EnterpriseR10BindingStoreError(
            "Binding store audit must be a list."
        )

    _validate_secret_free(raw)

    return raw


def save_enterprise_r10_binding_store(
    data: dict[str, Any],
    path: Path | None = None,
) -> None:
    target = path or enterprise_r10_binding_store_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": ENTERPRISE_R10_BINDING_STORE_VERSION,
        "bindings": list(data.get("bindings") or []),
        "audit": list(data.get("audit") or []),
    }

    _validate_secret_free(payload)

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)

        os.replace(temporary_path, target)

    except OSError:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

        raise


def _required_identifier(
    field_name: str,
    value: Any,
) -> str:
    normalized = str(value or "").strip()

    if not normalized:
        raise EnterpriseR10BindingStoreError(
            f"{field_name}_required"
        )

    return normalized


def record_enterprise_r10_binding(
    plan: dict[str, Any],
    *,
    actor: str,
    path: Path | None = None,
) -> dict[str, Any]:
    """Persist one validated secret-free binding plan."""

    if plan.get("binding_status") != "validated":
        raise EnterpriseR10BindingStoreError(
            "binding_plan_not_validated"
        )

    actor = _required_identifier("actor", actor)

    institution_case_id = _required_identifier(
        "institution_case_id",
        plan.get("institution_case_id"),
    )
    institution_task_id = _required_identifier(
        "institution_task_id",
        plan.get("institution_task_id"),
    )
    qualification_grant_id = _required_identifier(
        "qualification_grant_id",
        plan.get("qualification_grant_id"),
    )
    client_id = _required_identifier(
        "client_id",
        plan.get("client_id"),
    )
    external_case_id = _required_identifier(
        "external_connectivity_case_id",
        plan.get("external_connectivity_case_id"),
    )
    operational_profile_id = _required_identifier(
        "operational_profile_id",
        plan.get("operational_profile_id"),
    )

    if plan.get("target_environment") != "sandbox":
        raise EnterpriseR10BindingStoreError(
            "binding_environment_not_sandbox"
        )

    unsafe_flags = (
        bool(plan.get("production_allowed")),
        bool(plan.get("runtime_connector_approved")),
        bool(plan.get("external_http_allowed")),
        bool(plan.get("write_allowed")),
        bool(plan.get("restricted_allowed")),
        bool(plan.get("raw_secret_visible")),
    )

    if any(unsafe_flags):
        raise EnterpriseR10BindingStoreError(
            "unsafe_binding_plan"
        )

    store = load_enterprise_r10_binding_store(path)

    duplicate = next(
        (
            item
            for item in store["bindings"]
            if isinstance(item, dict)
            and item.get("institution_case_id")
            == institution_case_id
            and item.get("institution_task_id")
            == institution_task_id
            and item.get("status")
            not in {"revoked", "superseded"}
        ),
        None,
    )

    if duplicate is not None:
        raise EnterpriseR10BindingStoreError(
            "active_task_binding_already_exists"
        )

    prior_bindings = [
        item
        for item in store["bindings"]
        if isinstance(item, dict)
        and item.get("institution_case_id")
        == institution_case_id
        and item.get("institution_task_id")
        == institution_task_id
    ]

    previous_binding = (
        prior_bindings[-1]
        if prior_bindings
        else None
    )

    revision = len(prior_bindings) + 1
    previous_binding_id = (
        str(previous_binding.get("binding_id") or "")
        if previous_binding is not None
        else ""
    ) or None

    existing_binding_ids = {
        str(item.get("binding_id") or "")
        for item in store["bindings"]
        if isinstance(item, dict)
    }

    binding_id = ""
    for _ in range(5):
        candidate = f"er10bind_{uuid4().hex}"
        if candidate not in existing_binding_ids:
            binding_id = candidate
            break

    if not binding_id:
        raise EnterpriseR10BindingStoreError(
            "binding_id_generation_failed"
        )

    now = datetime.now(UTC).isoformat()

    binding = {
        "binding_id": binding_id,
        "revision": revision,
        "previous_binding_id": previous_binding_id,
        "institution_case_id": institution_case_id,
        "institution_task_id": institution_task_id,
        "qualification_grant_id": (
            qualification_grant_id
        ),
        "client_id": client_id,
        "integration_track": str(
            plan.get("integration_track") or ""
        ),
        "external_connectivity_case_id": (
            external_case_id
        ),
        "connector_id": str(
            plan.get("connector_id") or ""
        ),
        "operational_profile_id": (
            operational_profile_id
        ),
        "target_environment": "sandbox",
        "requested_scope_ids": list(
            plan.get("requested_scope_ids") or []
        ),
        "external_case_state": str(
            plan.get("external_case_state") or ""
        ),
        "next_required_state": str(
            plan.get("next_required_state") or ""
        ),
        "external_qualification_key_id": None,
        "external_sandbox_api_key_id": None,
        "status": "validated",
        "created_at": now,
        "updated_at": now,
        "created_by": actor,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }

    _validate_secret_free(binding)

    store["bindings"].append(binding)
    store["audit"].append(
        {
            "event": "enterprise_r10_binding_created",
            "binding_id": binding_id,
            "revision": revision,
            "previous_binding_id": previous_binding_id,
            "institution_case_id": institution_case_id,
            "institution_task_id": institution_task_id,
            "qualification_grant_id": (
                qualification_grant_id
            ),
            "client_id": client_id,
            "external_connectivity_case_id": (
                external_case_id
            ),
            "actor": actor,
            "occurred_at": now,
            "production_allowed": False,
            "runtime_connector_approved": False,
            "external_http_allowed": False,
            "raw_secret_visible": False,
        }
    )

    save_enterprise_r10_binding_store(
        store,
        path,
    )

    return safe_enterprise_r10_binding_projection(
        binding
    )


def update_enterprise_r10_binding_references(
    binding_id: str,
    *,
    external_case_state: str,
    next_required_state: str,
    external_qualification_key_id: str | None = None,
    external_sandbox_api_key_id: str | None = None,
    status: str,
    actor: str,
    path: Path | None = None,
) -> dict[str, Any]:
    """Update safe lifecycle references after an R10 operation."""

    binding_id = _required_identifier(
        "binding_id",
        binding_id,
    )
    actor = _required_identifier("actor", actor)

    allowed_statuses = {
        "validated",
        "qualification_key_issued",
        "qualification_redeemed",
        "sandbox_api_key_issued",
        "suspended",
        "revoked",
        "superseded",
    }

    if status not in allowed_statuses:
        raise EnterpriseR10BindingStoreError(
            "binding_status_invalid"
        )

    store = load_enterprise_r10_binding_store(path)

    binding = next(
        (
            item
            for item in store["bindings"]
            if isinstance(item, dict)
            and item.get("binding_id") == binding_id
        ),
        None,
    )

    if binding is None:
        raise EnterpriseR10BindingStoreError(
            "enterprise_r10_binding_not_found"
        )

    now = datetime.now(UTC).isoformat()

    binding.update(
        {
            "external_case_state": str(
                external_case_state or ""
            ),
            "next_required_state": str(
                next_required_state or ""
            ),
            "external_qualification_key_id": (
                str(
                    external_qualification_key_id
                    or ""
                )
                or None
            ),
            "external_sandbox_api_key_id": (
                str(
                    external_sandbox_api_key_id
                    or ""
                )
                or None
            ),
            "status": status,
            "updated_at": now,
            "updated_by": actor,
            "production_allowed": False,
            "runtime_connector_approved": False,
            "external_http_allowed": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "raw_secret_visible": False,
        }
    )

    _validate_secret_free(binding)

    store["audit"].append(
        {
            "event": "enterprise_r10_binding_updated",
            "binding_id": binding_id,
            "institution_case_id": binding[
                "institution_case_id"
            ],
            "institution_task_id": binding[
                "institution_task_id"
            ],
            "client_id": binding["client_id"],
            "status": status,
            "actor": actor,
            "occurred_at": now,
            "production_allowed": False,
            "runtime_connector_approved": False,
            "external_http_allowed": False,
            "raw_secret_visible": False,
        }
    )

    save_enterprise_r10_binding_store(
        store,
        path,
    )

    return safe_enterprise_r10_binding_projection(
        binding
    )


def list_safe_enterprise_r10_bindings(
    *,
    client_id: str | None = None,
    institution_case_id: str | None = None,
    institution_task_id: str | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    store = load_enterprise_r10_binding_store(path)
    results: list[dict[str, Any]] = []

    for binding in store["bindings"]:
        if not isinstance(binding, dict):
            continue

        if (
            client_id is not None
            and binding.get("client_id") != client_id
        ):
            continue

        if (
            institution_case_id is not None
            and binding.get("institution_case_id")
            != institution_case_id
        ):
            continue

        if (
            institution_task_id is not None
            and binding.get("institution_task_id")
            != institution_task_id
        ):
            continue

        results.append(
            safe_enterprise_r10_binding_projection(
                binding
            )
        )

    return results


def safe_enterprise_r10_binding_projection(
    binding: dict[str, Any],
) -> dict[str, Any]:
    result = dict(binding)

    result.update(
        {
            "production_allowed": False,
            "runtime_connector_approved": False,
            "external_http_allowed": False,
            "write_allowed": False,
            "restricted_allowed": False,
            "raw_secret_visible": False,
        }
    )

    _validate_secret_free(result)

    return result
