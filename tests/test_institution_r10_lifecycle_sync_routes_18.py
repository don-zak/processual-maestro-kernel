from __future__ import annotations

from fastapi.testclient import TestClient

from processual_api.main import app

EXPECTED_PATH = (
    "/settings/client/integration-cases/"
    "{case_id}/tasks/{task_id}/r10-binding/"
    "{binding_id}/sync"
)


def test_lifecycle_sync_openapi_contract() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})

    assert EXPECTED_PATH in paths
    assert "post" in paths[EXPECTED_PATH]
    assert "requestBody" not in paths[
        EXPECTED_PATH
    ]["post"]


def test_lifecycle_sync_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post(

            "/settings/client/integration-cases/"
            "missing-case/tasks/missing-task/"
            "r10-binding/missing-binding/sync"

    )

    assert response.status_code in {401, 403}
    assert response.status_code not in {404, 405}
