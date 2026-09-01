from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from processual_api.routers import evaluation_runtime
from processual_api.routers import settings as settings_router
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as binding_runtime
from processual_api.routers import settings_enterprise_sandbox_operational_runtime as sandbox_runtime
from processual_api.services import evaluation_runtime_delivery as delivery
from processual_api.services.evaluation_grants import (
    EVALUATION_EXECUTION_MODE,
    EVALUATION_GRANTS_STORAGE_KEY,
)


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


def _runtime_identity() -> dict:
    return {
        "sub": "owner-a",
        "user_id": "owner-a",
        "client_id": "client-a",
        "auth_method": "api_key",
        "api_key_id": "key-a",
        "entitlement_source": "admin_evaluation_grant",
        "evaluation_grant_id": "grant-a",
        "subscription_required": False,
        "allowed_task_ids": ["crm.customer_context"],
        "allowed_binding_ids": ["binding-a"],
        "scopes": ["run:evaluation"],
    }


def _runtime_raw() -> dict:
    return {
        EVALUATION_GRANTS_STORAGE_KEY: [
            {
                "grant_id": "grant-a",
                "status": "active",
                "client_id": "client-a",
                "allowed_scopes": ["run:evaluation"],
                "allowed_endpoints": [
                    {"method": "POST", "path": "/evaluation/runtime/task-execute"},
                ],
                "allowed_task_ids": ["crm.customer_context"],
                "allowed_binding_ids": ["binding-a"],
                "max_requests": 20,
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "execution_mode": EVALUATION_EXECUTION_MODE,
                "real_runtime_execution": True,
                "production_allowed": False,
            }
        ]
    }


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
        delivery.EvaluationIdempotencyConflictError,
        match="evaluation_idempotency_key_payload_mismatch",
    ):
        _claim(fingerprint=_fingerprint({"customer_id": "different"}))


def test_inflight_replay_is_blocked(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)
    _claim()

    with pytest.raises(
        delivery.EvaluationReplayBlockedError,
        match="evaluation_replay_blocked_executing",
    ):
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

    with pytest.raises(
        delivery.EvaluationReplayBlockedError,
        match="evaluation_replay_blocked_failed",
    ):
        _claim()


def test_concurrent_duplicate_claim_allows_exactly_one_executor(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)

    def attempt() -> str:
        try:
            return str(_claim()["status"])
        except delivery.EvaluationReplayBlockedError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _value: attempt(), range(2)))

    assert sorted(outcomes) == ["blocked", "claimed"]


def test_fingerprint_is_canonical_for_equivalent_mapping_order() -> None:
    first = _fingerprint({"a": 1, "nested": {"x": 2, "y": 3}})
    second = _fingerprint({"nested": {"y": 3, "x": 2}, "a": 1})
    assert first == second


def test_runtime_completed_replay_never_reaches_network_transport(monkeypatch) -> None:
    raw = _runtime_raw()
    spec = SimpleNamespace(
        binding_id="binding-a",
        task_id="crm.customer_context",
        method="GET",
        adapter_contract_id="adapter-a",
    )
    monkeypatch.setattr(settings_router, "_load_raw", lambda _owner_id: raw)
    monkeypatch.setattr(binding_runtime, "_find_binding", lambda _raw, _binding_id: spec)
    monkeypatch.setattr(binding_runtime, "_find_request_mapping", lambda _raw, _binding_id: None)
    monkeypatch.setattr(sandbox_runtime, "_content_contract", lambda _raw, _binding_id: {"ok": True})
    monkeypatch.setattr(
        sandbox_runtime,
        "_secret_reference",
        lambda _raw, _binding_id: {"ref": "secret"},
    )
    monkeypatch.setattr(
        evaluation_runtime,
        "resolve_active_sandbox_execution_grant",
        lambda _raw, *, binding_id, task_id: {
            "grant_id": "sandbox-grant-a",
            "approved_operation_classes": ["read"],
        },
    )

    async def replay_claim(**_kwargs):
        return {
            "status": "replay",
            "record": {"record_id": "record-a"},
            "response": {"execution_id": "exec-1", "evaluation_runtime": True},
        }

    monkeypatch.setattr(
        evaluation_runtime,
        "claim_evaluation_execution",
        replay_claim,
    )

    async def forbidden_execute(*_args, **_kwargs):
        raise AssertionError("network execution must not run for a completed replay")

    monkeypatch.setattr(evaluation_runtime, "execute_sandbox_binding", forbidden_execute)

    result = asyncio.run(
        evaluation_runtime.execute_evaluation_runtime_task(
            body=evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
                task_id="crm.customer_context",
                binding_id="binding-a",
                idempotency_key="request-replay-001",
                task_input={"customer_id": "123"},
            ),
            current_user=_runtime_identity(),
        )
    )

    assert result["execution_id"] == "exec-1"
    assert result["idempotent_replay"] is True
