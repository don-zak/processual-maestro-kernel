from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from processual_api.services import evaluation_runtime_delivery as delivery


def _fingerprint(task_input: dict | None = None) -> str:
    return delivery.evaluation_request_fingerprint(
        grant_id="grant-a",
        api_key_id="key-a",
        task_id="crm.customer_context",
        binding_id="binding-a",
        task_input=task_input or {"customer_id": "123"},
    )


def _claim(*, idempotency_key: str = "request-0001", fingerprint: str | None = None):
    return delivery.claim_evaluation_execution(
        owner_id="owner-a",
        grant_id="grant-a",
        api_key_id="key-a",
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint or _fingerprint(),
        task_id="crm.customer_context",
        binding_id="binding-a",
    )


def test_completed_execution_replays_without_raw_input(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)
    claimed = _claim()
    record_id = claimed["record"]["record_id"]

    delivery.complete_evaluation_execution(
        owner_id="owner-a",
        record_id=record_id,
        evidence={"execution_id": "exec-1", "response_sha256": "abc"},
        replay_response={"execution_id": "exec-1", "ok": True},
    )

    replay = _claim()
    assert replay["status"] == "replay"
    assert replay["response"] == {"execution_id": "exec-1", "ok": True}
    record = replay["record"]
    assert record["state"] == delivery.EVALUATION_DELIVERY_STATE_EVIDENCE_PERSISTED
    assert record["raw_task_input_persisted"] is False
    assert record["raw_secret_visible"] is False
    assert "task_input" not in record
    assert record["idempotency_key_sha256"] != "request-0001"


def test_idempotency_key_payload_mismatch_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)
    _claim()

    with pytest.raises(
        delivery.EvaluationIdempotencyConflict,
        match="evaluation_idempotency_key_payload_mismatch",
    ):
        _claim(fingerprint=_fingerprint({"customer_id": "different"}))


def test_inflight_replay_is_blocked(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)
    _claim()

    with pytest.raises(delivery.EvaluationReplayBlocked, match="evaluation_replay_blocked_executing"):
        _claim()


def test_failed_or_uncertain_execution_cannot_automatically_replay(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)
    claimed = _claim()
    delivery.fail_evaluation_execution(
        owner_id="owner-a",
        record_id=claimed["record"]["record_id"],
        failure_code="SandboxExecutionError",
    )

    with pytest.raises(delivery.EvaluationReplayBlocked, match="evaluation_replay_blocked_failed"):
        _claim()


def test_concurrent_duplicate_claim_allows_exactly_one_executor(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)

    def attempt() -> str:
        try:
            return str(_claim()["status"])
        except delivery.EvaluationReplayBlocked:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _value: attempt(), range(2)))

    assert sorted(outcomes) == ["blocked", "claimed"]


def test_fingerprint_is_canonical_for_equivalent_mapping_order() -> None:
    first = _fingerprint({"a": 1, "nested": {"x": 2, "y": 3}})
    second = _fingerprint({"nested": {"y": 3, "x": 2}, "a": 1})
    assert first == second
