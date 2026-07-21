from __future__ import annotations

from fastapi.testclient import TestClient

from processual_api.main import app

EXPECTED_PATH = (
    "/settings/client/integration-cases/"
    "{case_id}/tasks/{task_id}/r10-binding/"
    "{binding_id}/controlled-sandbox-qualification"
)


def test_controlled_sandbox_openapi_contract() -> None:
    schema = app.openapi()
    operation = schema["paths"][EXPECTED_PATH]["post"]

    assert "requestBody" not in operation


def test_controlled_sandbox_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post(
        "/settings/client/integration-cases/"
        "missing-case/tasks/missing-task/"
        "r10-binding/missing-binding/"
        "controlled-sandbox-qualification"
    )

    assert response.status_code in {401, 403}
