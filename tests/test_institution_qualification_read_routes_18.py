import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.main import app
from processual_api.routers import institution_qualification_18

client = TestClient(app)


def _write_case(
    data_dir: Path,
    *,
    owner: str = "user_demo",
    client_id: str = "client_demo",
) -> None:
    payload = {
        "institution_integration_cases": [
            {
                "case_id": "icase_demo",
                "client_id": client_id,
                "case_type": (
                    "camara_integration_case"
                ),
                "integration_track": "camara",
                "title": "CAMARA qualification",
                "status": "ready_for_review",
                "phase": "supervisor_decision",
                "tasks": [
                    {
                        "task_id": "capability_profile",
                        "status": "completed",
                        "validation": "passed",
                        "reference": "hidden-reference",
                        "note": "hidden-note",
                    }
                ],
                "created_at": (
                    "2026-07-20T10:00:00+00:00"
                ),
                "updated_at": (
                    "2026-07-20T11:00:00+00:00"
                ),
            }
        ]
    }

    (
        data_dir
        / f"settings_{owner}.json"
    ).write_text(
        json.dumps(payload) + "\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _restore_app_dependency_overrides():
    original_overrides = dict(
        app.dependency_overrides
    )

    try:
        yield
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(
            original_overrides
        )


def _override_user(payload: dict):
    def dependency() -> dict:
        return payload

    app.dependency_overrides[
        get_current_user
    ] = dependency


def test_admin_queue_requires_authentication() -> None:
    app.dependency_overrides.clear()

    response = client.get(
        "/settings/admin/integration-cases/"
        "qualification-queue"
    )

    assert response.status_code == 401


def test_admin_queue_requires_admin_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_user(
        {
            "sub": "user_demo",
            "client_id": "client_demo",
            "role": "client",
            "scopes": ["settings:read"],
        }
    )

    response = client.get(
        "/settings/admin/integration-cases/"
        "qualification-queue"
    )

    assert response.status_code == 403


def test_admin_queue_returns_safe_projection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_user(
        {
            "sub": "admin_demo",
            "role": "admin",
            "scopes": [
                "admin:integration:"
                "qualification:read"
            ],
        }
    )

    response = client.get(
        "/settings/admin/integration-cases/"
        "qualification-queue"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["queue_count"] == 1

    serialized = json.dumps(
        payload
    ).lower()

    assert "hidden-reference" not in serialized
    assert "hidden-note" not in serialized
    assert "raw_key" not in serialized
    assert "key_hash" not in serialized

    assert (
        payload["production_allowed"]
        is False
    )
    assert (
        payload[
            "runtime_connector_approved"
        ]
        is False
    )


def test_unknown_admin_case_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )

    _override_user(
        {
            "sub": "admin_demo",
            "role": "admin",
            "scopes": ["admin:*"],
        }
    )

    response = client.get(
        "/settings/admin/integration-cases/"
        "missing/qualification"
    )

    assert response.status_code == 404


def test_client_can_read_own_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_user(
        {
            "sub": "user_demo",
            "client_id": "client_demo",
            "role": "client",
            "scopes": ["settings:read"],
        }
    )

    response = client.get(
        "/settings/client/integration-cases/"
        "icase_demo/qualification"
    )

    assert response.status_code == 200
    assert (
        response.json()["case"]["case_id"]
        == "icase_demo"
    )


def test_client_cannot_read_other_owner_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_user(
        {
            "sub": "other_user",
            "client_id": "client_demo",
            "role": "client",
            "scopes": ["settings:read"],
        }
    )

    response = client.get(
        "/settings/client/integration-cases/"
        "icase_demo/qualification"
    )

    assert response.status_code == 404


def test_client_cannot_read_other_client_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_user(
        {
            "sub": "user_demo",
            "client_id": "client_other",
            "role": "client",
            "scopes": ["settings:read"],
        }
    )

    response = client.get(
        "/settings/client/integration-cases/"
        "icase_demo/task-credentials"
    )

    assert response.status_code == 404
