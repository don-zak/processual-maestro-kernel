from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

import processual_api.main as main_module
from processual_api.main import app
from processual_api.services import integration_pilot_controls

INTEGRATION_BODY_PATHS = (
    "/settings/admin/integration-tasks",
    "/settings/admin/integration-tasks/{task_id}/suspend",
    "/settings/admin/integration-tasks/{task_id}/resume",
    "/settings/admin/integration-tasks/{task_id}/revoke",
    "/settings/admin/integration-tasks/{task_id}/cancel",
    (
        "/settings/admin/integration-tasks/"
        "{task_id}/activation-permission-key"
    ),
)

CONTROL_CASES = (
    ("suspend", "suspend"),
    ("resume", "resume"),
    ("revoke", "revoke"),
    ("cancel", "cancel"),
)


def _resolve_schema(
    openapi: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    current = schema
    seen: set[str] = set()

    while "$ref" in current:
        reference = str(current["$ref"])
        assert reference.startswith("#/")
        assert reference not in seen
        seen.add(reference)

        resolved: Any = openapi

        for raw_segment in reference[2:].split("/"):
            segment = raw_segment.replace("~1", "/").replace("~0", "~")
            resolved = resolved[segment]

        assert isinstance(resolved, dict)
        current = resolved

    return current


@pytest.fixture
def approved_supervisor(monkeypatch: pytest.MonkeyPatch) -> None:
    def approve(_request: object) -> dict[str, object]:
        return {
            "session_key_id": "supsk_r7_contract_test",
            "validated": True,
        }

    monkeypatch.setattr(
        main_module,
        "_pmk13b_require_supervisor_write",
        approve,
    )


def test_openapi_declares_optional_json_body_for_integration_writes() -> None:
    openapi = app.openapi()

    for path in INTEGRATION_BODY_PATHS:
        operation = openapi["paths"][path]["post"]
        request_body = operation.get("requestBody")

        assert isinstance(request_body, dict), path
        assert request_body.get("required", False) is False, path
        assert "application/json" in request_body["content"], path

    control_operation = openapi["paths"][
        "/settings/admin/integration-tasks/{task_id}/suspend"
    ]["post"]

    control_schema = _resolve_schema(
        openapi,
        control_operation["requestBody"]["content"]["application/json"][
            "schema"
        ],
    )

    assert "reason" in control_schema["properties"]
    assert control_schema["properties"]["reason"].get("default") == ""


def test_create_accepts_missing_body_as_empty_object(
    monkeypatch: pytest.MonkeyPatch,
    approved_supervisor: None,
) -> None:
    captured: dict[str, Any] = {}

    def fake_create(
        payload: dict[str, Any],
        *,
        created_by: str,
    ) -> dict[str, Any]:
        captured["payload"] = payload
        captured["created_by"] = created_by
        return {
            "task_id": "task_r7_create",
            "created": True,
        }

    monkeypatch.setattr(
        integration_pilot_controls,
        "create_integration_task",
        fake_create,
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/settings/admin/integration-tasks")

    assert response.status_code == 200
    assert captured == {
        "payload": {},
        "created_by": "supsk_r7_contract_test",
    }


@pytest.mark.parametrize(("suffix", "expected_action"), CONTROL_CASES)
def test_control_routes_accept_missing_body_with_empty_reason(
    monkeypatch: pytest.MonkeyPatch,
    approved_supervisor: None,
    suffix: str,
    expected_action: str,
) -> None:
    captured: dict[str, Any] = {}

    def fake_control(
        task_id: str,
        action: str,
        *,
        actor: str,
        reason: str,
    ) -> dict[str, Any]:
        captured.update(
            {
                "task_id": task_id,
                "action": action,
                "actor": actor,
                "reason": reason,
            }
        )
        return {
            "task_id": task_id,
            "action": action,
        }

    monkeypatch.setattr(
        integration_pilot_controls,
        "control_integration_task",
        fake_control,
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/settings/admin/integration-tasks/task_r7/{suffix}"
    )

    assert response.status_code == 200
    assert captured == {
        "task_id": "task_r7",
        "action": expected_action,
        "actor": "supsk_r7_contract_test",
        "reason": "",
    }


def test_activation_key_route_accepts_missing_body_as_empty_object(
    monkeypatch: pytest.MonkeyPatch,
    approved_supervisor: None,
) -> None:
    captured: dict[str, Any] = {}

    def fake_issue(
        task_id: str,
        payload: dict[str, Any],
        *,
        issued_by: str,
    ) -> dict[str, Any]:
        captured.update(
            {
                "task_id": task_id,
                "payload": payload,
                "issued_by": issued_by,
            }
        )
        return {
            "task_id": task_id,
            "issued": True,
        }

    monkeypatch.setattr(
        integration_pilot_controls,
        "issue_activation_permission_key",
        fake_issue,
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/settings/admin/integration-tasks/"
        "task_r7/activation-permission-key"
    )

    assert response.status_code == 200
    assert captured == {
        "task_id": "task_r7",
        "payload": {},
        "issued_by": "supsk_r7_contract_test",
    }


def test_malformed_json_returns_422_without_service_write(
    monkeypatch: pytest.MonkeyPatch,
    approved_supervisor: None,
) -> None:
    service_calls = 0

    def fake_create(
        _payload: dict[str, Any],
        *,
        created_by: str,
    ) -> dict[str, Any]:
        nonlocal service_calls
        service_calls += 1
        return {"created_by": created_by}

    monkeypatch.setattr(
        integration_pilot_controls,
        "create_integration_task",
        fake_create,
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/settings/admin/integration-tasks",
        content=b"{",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert service_calls == 0


def test_supervisor_revoke_contract_remains_required_and_typed() -> None:
    openapi = app.openapi()
    operation = openapi["paths"][
        "/settings/admin/supervisor-session-keys/"
        "{session_key_id}/revoke"
    ]["post"]

    request_body = operation["requestBody"]
    schema = request_body["content"]["application/json"]["schema"]

    assert request_body["required"] is True
    assert schema["$ref"].endswith("/SupervisorSessionKeyRevokeRequest")
