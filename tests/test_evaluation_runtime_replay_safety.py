from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from processual_api.routers import evaluation_runtime
from processual_api.services import evaluation_runtime_delivery as delivery


def test_runtime_safe_replay_receipt_excludes_canonical_input() -> None:
    response = {
        "execution_id": "exec-1",
        "canonical_input": {"customer": {"email": "private@example.test"}},
        "canonical_input_sha256": "digest",
        "raw_response_included": False,
        "raw_secret_visible": False,
        "evaluation_runtime": True,
    }

    safe = evaluation_runtime._safe_replay_response(response)

    assert "canonical_input" not in safe
    assert safe["canonical_input_sha256"] == "digest"
    assert safe["canonical_input_included"] is False
    assert safe["raw_response_included"] is False
    assert safe["raw_secret_visible"] is False


def test_delivery_ledger_rejects_sensitive_replay_payload(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(delivery, "_DATA_DIR", tmp_path)
    fingerprint = delivery.evaluation_request_fingerprint(
        grant_id="grant-a",
        api_key_id="key-a",
        task_id="crm.customer_context",
        binding_id="binding-a",
        task_input={"customer_id": "123"},
    )
    claimed = delivery.claim_evaluation_execution(
        owner_id="owner-a",
        grant_id="grant-a",
        api_key_id="key-a",
        idempotency_key="request-sensitive-001",
        request_fingerprint=fingerprint,
        task_id="crm.customer_context",
        binding_id="binding-a",
    )

    with pytest.raises(
        delivery.EvaluationDeliveryError,
        match="evaluation_replay_payload_contains_sensitive_material",
    ):
        delivery.complete_evaluation_execution(
            owner_id="owner-a",
            record_id=claimed["record"]["record_id"],
            evidence={"execution_id": "exec-1"},
            replay_response={"canonical_input": {"secret": "must-not-persist"}},
        )


def test_idempotency_key_is_trimmed_and_whitespace_only_is_rejected() -> None:
    request = evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
        task_id="crm.customer_context",
        binding_id="binding-a",
        idempotency_key="  request-001  ",
        task_input={},
    )
    assert request.idempotency_key == "request-001"

    with pytest.raises(ValidationError):
        evaluation_runtime.EvaluationRuntimeTaskExecuteRequest(
            task_id="crm.customer_context",
            binding_id="binding-a",
            idempotency_key="        ",
            task_input={},
        )
