from __future__ import annotations

from fastapi.testclient import TestClient

from processual_api.main import app

EXPECTED_PATH = (
    "/settings/client/integration-cases/"
    "{case_id}/tasks/{task_id}/r10-binding"
)


def test_binding_creation_openapi_contract() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})

    assert EXPECTED_PATH in paths
    assert "post" in paths[EXPECTED_PATH]

    operation = paths[EXPECTED_PATH]["post"]
    assert operation["operationId"].startswith(
        "create_client_r10_binding_18"
    )


def test_binding_creation_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post(
        (
            "/settings/client/integration-cases/"
            "missing-case/tasks/missing-task/"
            "r10-binding"
        ),
        json={
            "external_connectivity_case_id": (
                "missing-external-case"
            )
        },
    )

    assert response.status_code in {401, 403}
    assert response.status_code not in {404, 405}


def test_binding_request_does_not_accept_authority_fields() -> None:
    schema = app.openapi()
    operation = schema["paths"][
        EXPECTED_PATH
    ]["post"]

    request_schema_ref = operation[
        "requestBody"
    ]["content"]["application/json"]["schema"]["$ref"]

    schema_name = request_schema_ref.rsplit("/", 1)[-1]
    request_schema = schema["components"]["schemas"][
        schema_name
    ]

    assert set(request_schema["properties"]) == {
        "external_connectivity_case_id"
    }
