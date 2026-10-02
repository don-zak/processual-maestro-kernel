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


def test_owned_crm_proof_executes_exactly_once_on_success(monkeypatch) -> None:
    attempts = 0

    async def fake_execute(**kwargs):
        nonlocal attempts
        attempts += 1
        assert kwargs["binding_id"] == "evaluation.crm.customer_context.owned"
        return {"status": "sandbox_proof_passed"}

    monkeypatch.setattr(preset, "execute_evaluation_sandbox_operational_proof", fake_execute)

    result = asyncio.run(
        preset._execute_owned_proof_once(
            binding_id="evaluation.crm.customer_context.owned",
            body=_body(),
            request=object(),
            current_user={"sub": "admin"},
        )
    )

    assert result == {"status": "sandbox_proof_passed"}
    assert attempts == 1


@pytest.mark.parametrize(
    "detail",
    [
        "sandbox_http_status_not_allowed:429",
        "sandbox_response_not_json",
        "sandbox_peer_address_mismatch",
    ],
)
def test_owned_crm_proof_never_retries_failures(monkeypatch, detail: str) -> None:
    attempts = 0

    async def fake_execute(**kwargs):
        nonlocal attempts
        attempts += 1
        raise HTTPException(status_code=422, detail=detail)

    monkeypatch.setattr(preset, "execute_evaluation_sandbox_operational_proof", fake_execute)

    with pytest.raises(HTTPException, match=detail):
        asyncio.run(
            preset._execute_owned_proof_once(
                binding_id="evaluation.crm.customer_context.owned",
                body=_body(),
                request=object(),
                current_user={"sub": "admin"},
            )
        )

    assert attempts == 1


def test_owned_crm_preset_has_no_retry_or_sleep_policy() -> None:
    source = __import__(
        "pathlib"
    ).Path(preset.__file__).read_text(encoding="utf-8")

    assert "_PROOF_MAX_ATTEMPTS" not in source
    assert "asyncio.sleep" not in source
    assert "_execute_owned_proof_with_retry" not in source
    assert "_execute_owned_proof_once" in source
