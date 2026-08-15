from __future__ import annotations

import json

from processual_api.services.evaluation_idempotency import (
    EVALUATION_IDEMPOTENCY_STORAGE_KEY,
    reserve_evaluation_execution,
    update_evaluation_execution_reservation,
)


def _reserve(raw: dict, *, key: str = "ticket-create-001", value: str = "a") -> dict:
    return reserve_evaluation_execution(
        raw,
        idempotency_key=key,
        task_id="support.ticket_create",
        binding_id="binding-support-write",
        task_input={"ticket_id": "ticket-1", "value": value},
        api_key_id="evalkey-1",
        evaluation_grant_id="eval-1",
    )


def test_first_non_read_execution_reserves_before_network_without_raw_payload() -> None:
    raw: dict = {}
    reservation = _reserve(raw)

    assert reservation["status"] == "reserved"
    stored = raw[EVALUATION_IDEMPOTENCY_STORAGE_KEY][0]
    serialized = json.dumps(stored, sort_keys=True)
    assert stored["state"] == "reserved_before_network"
    assert stored["raw_task_input_persisted"] is False
    assert stored["raw_idempotency_key_persisted"] is False
    assert "ticket-create-001" not in serialized
    assert '"value": "a"' not in serialized


def test_same_idempotency_key_and_request_is_blocked_as_duplicate() -> None:
    raw: dict = {}
    first = _reserve(raw)
    duplicate = _reserve(raw)

    assert first["status"] == "reserved"
    assert duplicate["status"] == "duplicate"
    assert duplicate["reservation_id"] == first["reservation_id"]
    assert duplicate["previous_state"] == "reserved_before_network"
    assert len(raw[EVALUATION_IDEMPOTENCY_STORAGE_KEY]) == 1


def test_same_idempotency_key_with_changed_payload_is_conflict() -> None:
    raw: dict = {}
    _reserve(raw, value="a")
    conflict = _reserve(raw, value="b")

    assert conflict["status"] == "conflict"
    assert conflict["previous_state"] == "reserved_before_network"
    assert len(raw[EVALUATION_IDEMPOTENCY_STORAGE_KEY]) == 1


def test_uncertain_failure_remains_reserved_against_silent_retry() -> None:
    raw: dict = {}
    first = _reserve(raw)
    update_evaluation_execution_reservation(
        raw,
        reservation_id=first["reservation_id"],
        state="network_or_response_failure_uncertain",
    )

    duplicate = _reserve(raw)
    assert duplicate["status"] == "duplicate"
    assert duplicate["previous_state"] == "network_or_response_failure_uncertain"


def test_completed_external_execution_is_still_deduplicated() -> None:
    raw: dict = {}
    first = _reserve(raw)
    update_evaluation_execution_reservation(
        raw,
        reservation_id=first["reservation_id"],
        state="external_execution_completed",
        execution_id="exec-1",
        evidence_sha256="a" * 64,
    )

    duplicate = _reserve(raw)
    stored = raw[EVALUATION_IDEMPOTENCY_STORAGE_KEY][0]
    assert duplicate["status"] == "duplicate"
    assert duplicate["previous_state"] == "external_execution_completed"
    assert stored["execution_id"] == "exec-1"
    assert stored["evidence_sha256"] == "a" * 64


def test_evaluation_runtime_requires_idempotency_only_for_non_read_tasks() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "processual_api"
        / "routers"
        / "evaluation_runtime.py"
    ).read_text(encoding="utf-8")

    assert "idempotency_key" in source
    assert 'non_read_task = str(task.operation_class) != "read"' in source
    assert "Non-READ Evaluation tasks require an idempotency_key" in source
    assert "Duplicate non-READ Evaluation execution blocked before network" in source
    assert "network_or_response_failure_uncertain" in source
    assert '"raw_task_input_persisted": False' in source
    assert '"raw_idempotency_key_persisted": False' in source
