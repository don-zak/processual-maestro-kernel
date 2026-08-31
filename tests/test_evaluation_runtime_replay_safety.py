from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from processual_api.routers import evaluation_runtime
from processual_api.services import evaluation_runtime_delivery as delivery
from processual_api.services.evaluation_grants import EVALUATION_GRANTS_STORAGE_KEY


def _evaluation_identity() -> dict:
    return {
        "auth_method": "api_key",
        "entitlement_source": "admin_evaluation_grant",
        "subscription_required": False,
        "evaluation_grant_id": "grant-a",
    }


def _grant(*, status_value: str = "active", expires_at: str | None = None) -> dict:
    return {
        "grant_id": "grant-a",
        "status": status_value,
        "expires_at": expires_at
        or (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "execution_mode": "evaluation_runtime",
        "real_runtime_execution": True,
        "production_allowed": False,
    }


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


def test_revoked_grant_is_revalidated_before_runtime_or_replay() -> None:
    raw = {EVALUATION_GRANTS_STORAGE_KEY: [_grant(status_value="revoked")]}

    with pytest.raises(HTTPException) as exc:
        evaluation_runtime._require_evaluation_credential(_evaluation_identity(), raw)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Evaluation runtime authority is unavailable."


def test_expired_grant_is_revalidated_before_runtime_or_replay() -> None:
    raw = {
        EVALUATION_GRANTS_STORAGE_KEY: [
            _grant(expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat())
        ]
    }

    with pytest.raises(HTTPException) as exc:
        evaluation_runtime._require_evaluation_credential(_evaluation_identity(), raw)

    assert exc.value.status_code == 403
    assert exc.value.detail == "Evaluation runtime authority is unavailable."
    assert raw[EVALUATION_GRANTS_STORAGE_KEY][0]["status"] == "expired"
