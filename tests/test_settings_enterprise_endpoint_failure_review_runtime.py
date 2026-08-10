from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from processual_api.integrations.enterprise_endpoint_bindings import BINDING_STORAGE_KEY
from processual_api.routers import settings as settings_module
from processual_api.routers import settings_enterprise_endpoint_failure_review_runtime as review_runtime
from processual_api.services.enterprise_endpoint_failure_review import FAILURE_STORAGE_KEY


def _client() -> dict:
    return {
        "sub": "client-a",
        "user_id": "client-a",
        "client_id": "client-a",
        "role": "client",
        "plan_id": "enterprise_core",
    }


def _admin() -> dict:
    return {
        "sub": "admin-a",
        "user_id": "admin-a",
        "role": "admin",
        "scopes": ["admin:integration:qualification:review"],
    }


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/settings/admin"})


def _raw() -> dict:
    return {
        "subscription": {"plan_id": "enterprise_core"},
        BINDING_STORAGE_KEY: [
            {
                "binding_id": "billing.account",
                "display_name": "Billing account",
                "adapter_contract_id": "billing",
                "task_id": "billing.account_context",
                "credential_profile_id": "enterprise_core_api_reference",
                "environment": "sandbox",
                "base_url": "https://sandbox.example.test/api",
                "method": "GET",
                "path": "/accounts/{account_id}",
                "required_scope_ids": ["billing:read"],
                "path_parameters": {"account_id": "$task.account_id"},
                "query_parameters": {},
                "request_headers": {"Accept": "application/json"},
                "response_format": "json",
                "response_data_path": "$.data",
                "field_mapping": {"account_id": "$.id"},
                "success_codes": [200],
                "timeout_seconds": 15,
            }
        ],
    }


def _failure() -> dict:
    return {
        "failure_id": "sbf_open",
        "binding_id": "billing.account",
        "task_id": "billing.account_context",
        "stage": "credential",
        "failure_code": "credential_unavailable",
        "recommended_action": "Verify the credential reference.",
        "retryable": True,
        "status": "open",
        "attempt": 1,
        "occurred_at": "2026-08-10T18:00:00+00:00",
        "last_reviewed_at": "",
        "resolution_code": "",
        "resolved_at": "",
        "evidence_sha256": "",
        "production_allowed": False,
        "raw_secret_visible": False,
        "raw_error_included": False,
    }


def test_reviewed_run_records_safe_failure_and_returns_action(monkeypatch) -> None:
    raw = _raw()
    saves: list[dict] = []
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(
        settings_module,
        "_save_raw",
        lambda user_id, value: saves.append(dict(value)),
    )

    async def fail(*args, **kwargs):
        raise HTTPException(
            status_code=422,
            detail="sandbox_credential_reference_unresolved",
        )

    monkeypatch.setattr(
        review_runtime.endpoint_runtime,
        "execute_enterprise_endpoint_sandbox_proof",
        fail,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            review_runtime.execute_enterprise_endpoint_reviewed_sandbox_proof(
                "billing.account",
                review_runtime.endpoint_runtime.EndpointSandboxExecuteRequest(
                    task_input={"account_id": "A-100"}
                ),
                _client(),
            )
        )

    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert detail["message"] == "Sandbox proof failed and was recorded for review."
    assert detail["failure"]["stage"] == "credential"
    assert detail["failure"]["failure_code"] == "credential_unavailable"
    assert detail["failure"]["raw_error_included"] is False
    assert len(raw[FAILURE_STORAGE_KEY]) == 1
    assert len(saves) == 1


def test_successful_reviewed_run_resolves_open_failures(monkeypatch) -> None:
    raw = _raw()
    raw[FAILURE_STORAGE_KEY] = [_failure()]
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(settings_module, "_save_raw", lambda user_id, value: None)

    async def pass_run(*args, **kwargs):
        return {
            "status": "sandbox_proof_passed",
            "binding_id": "billing.account",
            "task_id": "billing.account_context",
            "evidence_sha256": "e" * 64,
            "production_allowed": False,
            "runtime_connector_approved": False,
        }

    monkeypatch.setattr(
        review_runtime.endpoint_runtime,
        "execute_enterprise_endpoint_sandbox_proof",
        pass_run,
    )

    result = asyncio.run(
        review_runtime.execute_enterprise_endpoint_reviewed_sandbox_proof(
            "billing.account",
            review_runtime.endpoint_runtime.EndpointSandboxExecuteRequest(
                task_input={"account_id": "A-100"}
            ),
            _client(),
        )
    )
    assert result["failure_review"]["resolved_failure_count"] == 1
    assert raw[FAILURE_STORAGE_KEY][0]["status"] == "resolved"
    assert raw[FAILURE_STORAGE_KEY][0]["evidence_sha256"] == "e" * 64


def test_failure_listing_exposes_counts_without_raw_error(monkeypatch) -> None:
    raw = _raw()
    raw[FAILURE_STORAGE_KEY] = [_failure()]
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    payload = asyncio.run(
        review_runtime.list_enterprise_endpoint_sandbox_failures(_client())
    )
    assert payload["failure_count"] == 1
    assert payload["open_count"] == 1
    assert payload["reviewing_count"] == 0
    assert payload["raw_error_visible"] is False
    assert "raw_error" not in payload["failures"][0]


def test_admin_failure_queue_requires_admin_read_scope(monkeypatch) -> None:
    raw = _raw()
    raw[FAILURE_STORAGE_KEY] = [_failure()]
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)

    payload = asyncio.run(
        review_runtime.list_admin_enterprise_endpoint_sandbox_failures(
            "client-a",
            _admin(),
        )
    )
    assert payload["client_id"] == "client-a"
    assert payload["visibility"] == "admin"
    assert payload["open_count"] == 1
    assert payload["raw_error_visible"] is False

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            review_runtime.list_admin_enterprise_endpoint_sandbox_failures(
                "client-a",
                {"role": "client", "scopes": []},
            )
        )
    assert exc_info.value.status_code == 403


def test_admin_start_review_changes_state_only_after_supervisor_guard(monkeypatch) -> None:
    raw = _raw()
    raw[FAILURE_STORAGE_KEY] = [_failure()]
    saves: list[dict] = []
    monkeypatch.setattr(settings_module, "_load_raw", lambda user_id: raw)
    monkeypatch.setattr(
        settings_module,
        "_save_raw",
        lambda user_id, value: saves.append(dict(value)),
    )
    supervisor_guard_calls: list[bool] = []
    monkeypatch.setattr(
        review_runtime,
        "_require_supervisor_review_session",
        lambda request: supervisor_guard_calls.append(True),
    )

    result = asyncio.run(
        review_runtime.review_enterprise_endpoint_sandbox_failure(
            "client-a",
            "sbf_open",
            _request(),
            _admin(),
        )
    )
    assert supervisor_guard_calls == [True]
    assert result["status"] == "reviewing"
    assert result["failure"]["status"] == "reviewing"
    assert result["failure"]["resolution_code"] == ""
    assert result["production_allowed"] is False
    assert len(saves) == 1
