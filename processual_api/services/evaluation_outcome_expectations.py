"""Hashed outcome expectations for governed External Evaluation READ tasks.

Expected synthetic values may be supplied transiently by the Super Administrator,
but only deterministic hashes and field names are persisted. Runtime validation
therefore proves that the mapped external result matches the prepared scenario
without storing the raw expected fixture values or the raw Evaluation API key.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY = "evaluation_outcome_expectations_v1"


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_outcome_expectation(
    *,
    binding_id: str,
    task_id: str,
    expected_fields: Mapping[str, Any],
    acceptance_criteria_references: tuple[str, ...],
    dataset_reference: str,
    fixture_profile_reference: str,
    created_by: str,
) -> dict[str, Any]:
    binding = str(binding_id or "").strip()
    task = str(task_id or "").strip().lower()
    fields = {str(key).strip(): value for key, value in expected_fields.items() if str(key).strip()}
    if not binding or not task:
        raise ValueError("binding_id and task_id are required")
    if not fields:
        raise ValueError("at least one expected field is required")
    if len(fields) > 32:
        raise ValueError("at most 32 expected fields are allowed")
    if not acceptance_criteria_references:
        raise ValueError("acceptance criteria references are required")

    hashed_fields = {key: _stable_hash(value) for key, value in sorted(fields.items())}
    expectation_payload = {
        "binding_id": binding,
        "task_id": task,
        "expected_field_sha256": hashed_fields,
        "required_fields": sorted(hashed_fields),
        "acceptance_criteria_references": list(acceptance_criteria_references),
        "dataset_reference": str(dataset_reference or "").strip(),
        "fixture_profile_reference": str(fixture_profile_reference or "").strip(),
    }
    expectation_sha256 = _stable_hash(expectation_payload)
    return {
        **expectation_payload,
        "expectation_sha256": expectation_sha256,
        "created_by": str(created_by or "platform_admin"),
        "created_at": datetime.now(UTC).isoformat(),
        "raw_expected_values_persisted": False,
        "production_allowed": False,
    }


def upsert_outcome_expectation(raw: dict[str, Any], expectation: dict[str, Any]) -> None:
    items = raw.get(EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY, [])
    if not isinstance(items, list):
        items = []
    binding_id = str(expectation.get("binding_id") or "")
    task_id = str(expectation.get("task_id") or "")
    items = [
        item
        for item in items
        if not (
            isinstance(item, dict)
            and str(item.get("binding_id") or "") == binding_id
            and str(item.get("task_id") or "") == task_id
        )
    ]
    items.append(expectation)
    raw[EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY] = items[-200:]


def find_outcome_expectation(
    raw: Mapping[str, Any],
    *,
    binding_id: str,
    task_id: str,
) -> dict[str, Any] | None:
    items = raw.get(EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY, [])
    if not isinstance(items, list):
        return None
    binding = str(binding_id or "")
    task = str(task_id or "").lower()
    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        if str(item.get("binding_id") or "") == binding and str(item.get("task_id") or "").lower() == task:
            return dict(item)
    return None


def validate_read_outcome(
    *,
    expectation: Mapping[str, Any] | None,
    canonical_result: Mapping[str, Any],
    acceptance_criteria_references: tuple[str, ...],
    dataset_reference: str,
    fixture_profile_reference: str,
) -> dict[str, Any]:
    if expectation is None:
        return {
            "outcome_validation_status": "missing_expectation",
            "outcome_validated": False,
            "outcome_validation_passed": False,
            "outcome_validation_sha256": None,
            "raw_expected_values_persisted": False,
            "production_allowed": False,
        }

    references_match = (
        list(expectation.get("acceptance_criteria_references") or [])
        == list(acceptance_criteria_references)
        and str(expectation.get("dataset_reference") or "") == str(dataset_reference or "")
        and str(expectation.get("fixture_profile_reference") or "") == str(fixture_profile_reference or "")
    )
    expected_hashes = expectation.get("expected_field_sha256") or {}
    if not isinstance(expected_hashes, dict):
        expected_hashes = {}

    checks: list[dict[str, Any]] = []
    for field_name, expected_hash in sorted(expected_hashes.items()):
        present = field_name in canonical_result
        actual_hash = _stable_hash(canonical_result.get(field_name)) if present else None
        checks.append(
            {
                "field": field_name,
                "present": present,
                "matched": bool(present and actual_hash == expected_hash),
            }
        )

    passed = bool(references_match and checks and all(check["matched"] for check in checks))
    validation_payload = {
        "expectation_sha256": expectation.get("expectation_sha256"),
        "references_match": references_match,
        "checks": checks,
        "passed": passed,
    }
    return {
        "outcome_validation_status": "passed" if passed else "failed",
        "outcome_validated": True,
        "outcome_validation_passed": passed,
        "outcome_validation_sha256": _stable_hash(validation_payload),
        "expectation_sha256": expectation.get("expectation_sha256"),
        "field_check_count": len(checks),
        "matched_field_count": sum(1 for check in checks if check["matched"]),
        "references_match": references_match,
        "raw_expected_values_persisted": False,
        "production_allowed": False,
    }


__all__ = [
    "EVALUATION_OUTCOME_EXPECTATIONS_STORAGE_KEY",
    "build_outcome_expectation",
    "find_outcome_expectation",
    "upsert_outcome_expectation",
    "validate_read_outcome",
]
