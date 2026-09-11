from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from processual_api.routers import settings_admin_evaluation_owned_sandbox_preset as preset
from processual_api.routers import settings_enterprise_endpoint_bindings_runtime as binding_runtime


def _body() -> binding_runtime.EndpointSandboxExecuteRequest:
    return binding_runtime.EndpointSandboxExecuteRequest(
        task_input={"customer_id": "sandbox-customer-001"}
    )


def test_owned_crm_proof_retries_transient_429_then_succeeds(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    async def fake_execute(**kwargs):
        nonlocal attempts
        attempts += 1
        assert kwargs["binding_id"] == "evaluation.crm.customer_context.owned"
        if attempts < 3:
            raise HTTPException(
                status_code=422,
                detail="sandbox_http_status_not_allowed:429",
            )
        return {"status": "sandbox_proof_passed"}

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(preset, "execute_evaluation_sandbox_operational_proof", fake_execute)
    monkeypatch.setattr(preset.asyncio, "sleep", fake_sleep)

    result = asyncio.run(
        preset._execute_owned_proof_with_retry(
            binding_id="evaluation.crm.customer_context.owned",
            body=_body(),
            request=object(),
            current_user={"sub": "admin"},
        )
    )

    assert result == {"status": "sandbox_proof_passed"}
    assert attempts == 3
    assert sleeps == [1.0, 2.0]


def test_owned_crm_proof_does_not_retry_non_429(monkeypatch) -> None:
    attempts = 0

    async def fake_execute(**kwargs):
        nonlocal attempts
        attempts += 1
        raise HTTPException(status_code=422, detail="sandbox_response_not_json")

    async def fail_sleep(delay: float) -> None:
        raise AssertionError(f"unexpected retry sleep: {delay}")

    monkeypatch.setattr(preset, "execute_evaluation_sandbox_operational_proof", fake_execute)
    monkeypatch.setattr(preset.asyncio, "sleep", fail_sleep)

    with pytest.raises(HTTPException, match="sandbox_response_not_json"):
        asyncio.run(
            preset._execute_owned_proof_with_retry(
                binding_id="evaluation.crm.customer_context.owned",
                body=_body(),
                request=object(),
                current_user={"sub": "admin"},
            )
        )
    assert attempts == 1


def test_owned_crm_proof_caps_429_retries(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    async def fake_execute(**kwargs):
        nonlocal attempts
        attempts += 1
        raise HTTPException(
            status_code=422,
            detail="sandbox_http_status_not_allowed:429",
        )

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(preset, "execute_evaluation_sandbox_operational_proof", fake_execute)
    monkeypatch.setattr(preset.asyncio, "sleep", fake_sleep)

    with pytest.raises(HTTPException, match="sandbox_http_status_not_allowed:429"):
        asyncio.run(
            preset._execute_owned_proof_with_retry(
                binding_id="evaluation.crm.customer_context.owned",
                body=_body(),
                request=object(),
                current_user={"sub": "admin"},
            )
        )

    assert attempts == preset._PROOF_MAX_ATTEMPTS
    assert sleeps == [1.0, 2.0]
