import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.main import app
from processual_api.routers import (
    institution_qualification_18,
)

client = TestClient(app)


def _write_case(
    data_dir: Path,
) -> None:
    payload = {
        "institution_integration_cases": [
            {
                "case_id": "icase_demo",
                "client_id": "client_demo",
                "integration_track": "camara",
                "title": "CAMARA qualification",
                "status": "ready_for_review",
                "phase": "supervisor_decision",
                "tasks": [
                    {
                        "task_id": (
                            "capability_profile"
                        ),
                        "status": "completed",
                        "validation": "passed",
                    },
                    {
                        "task_id": (
                            "sandbox_capability_probe"
                        ),
                        "status": "completed",
                        "validation": "passed",
                    },
                ],
            }
        ]
    }

    (
        data_dir
        / "settings_user_demo.json"
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

def _override_admin(
    *,
    scopes: list[str],
) -> None:
    def dependency() -> dict:
        return {
            "sub": "admin_demo",
            "email": "admin@example.test",
            "role": "admin",
            "scopes": scopes,
        }

    app.dependency_overrides[
        get_current_user
    ] = dependency


def _fake_session(
    *,
    scopes: set[str],
) -> dict:
    return {
        "session_present": True,
        "session_validated": True,
        "session_key_id": "supsk_demo",
        "provided_scopes": sorted(scopes),
        "required_scopes": sorted(scopes),
    }


def test_approve_requires_admin_scope(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_admin(
        scopes=["settings:read"]
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/approve",
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ]
        },
    )

    assert response.status_code == 403


def test_approve_requires_supervisor_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    _write_case(tmp_path)

    _override_admin(
        scopes=[
            "admin:integration:"
            "qualification:read"
        ]
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/approve",
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ]
        },
    )

    assert response.status_code == 403


def test_valid_approval_returns_safe_grant(
    tmp_path: Path,
    monkeypatch,
) -> None:
    qualification_path = (
        tmp_path / "qualification.json"
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setenv(
        "PMK_ENTERPRISE_QUALIFICATION_STORE_PATH",
        str(qualification_path),
    )

    _write_case(tmp_path)

    _override_admin(
        scopes=[
            "admin:integration:"
            "qualification:read"
        ]
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_require_qualification_write_session",
        lambda request, required_scope: (
            _fake_session(
                scopes={required_scope}
            )
        ),
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/approve",
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ],
            "reason": (
                "Validated sandbox readiness."
            ),
            "ttl_days": 7,
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["status"] == "approved"
    assert (
        payload["grant"]["case_id"]
        == "icase_demo"
    )
    assert (
        "supervisor_session_key_id"
        not in payload["grant"]
    )

    serialized = json.dumps(
        payload
    ).lower()

    assert "raw_key" not in serialized
    assert "key_hash" not in serialized
    assert "pmk_sup_" not in serialized

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


def test_reference_task_approval_is_rejected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setenv(
        "PMK_ENTERPRISE_QUALIFICATION_STORE_PATH",
        str(tmp_path / "qualification.json"),
    )

    _write_case(tmp_path)

    _override_admin(
        scopes=["admin:*"]
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_require_qualification_write_session",
        lambda request, required_scope: (
            _fake_session(
                scopes={required_scope}
            )
        ),
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/approve",
        json={
            "approved_task_ids": [
                "capability_profile"
            ]
        },
    )

    assert response.status_code == 422


def test_duplicate_active_grant_returns_conflict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setenv(
        "PMK_ENTERPRISE_QUALIFICATION_STORE_PATH",
        str(tmp_path / "qualification.json"),
    )

    _write_case(tmp_path)

    _override_admin(
        scopes=["admin:*"]
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_require_qualification_write_session",
        lambda request, required_scope: (
            _fake_session(
                scopes={required_scope}
            )
        ),
    )

    request_body = {
        "approved_task_ids": [
            "sandbox_capability_probe"
        ]
    }

    first = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/approve",
        json=request_body,
    )
    second = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/approve",
        json=request_body,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_revision_request_is_persisted_safely(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setenv(
        "PMK_ENTERPRISE_QUALIFICATION_STORE_PATH",
        str(tmp_path / "qualification.json"),
    )

    _write_case(tmp_path)

    _override_admin(
        scopes=[
            "admin:integration:"
            "qualification:read"
        ]
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_require_qualification_write_session",
        lambda request, required_scope: (
            _fake_session(
                scopes={required_scope}
            )
        ),
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_demo/qualification/"
        "request-revision",
        json={
            "reason": (
                "Correct the sandbox endpoint "
                "reference."
            )
        },
    )

    assert response.status_code == 200
    assert (
        response.json()["status"]
        == "revision_required"
    )

    serialized = json.dumps(
        response.json()
    ).lower()

    assert "raw_key" not in serialized
    assert "key_hash" not in serialized


def test_unknown_case_returns_not_found(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: tmp_path,
    )

    _override_admin(
        scopes=["admin:*"]
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_require_qualification_write_session",
        lambda request, required_scope: (
            _fake_session(
                scopes={required_scope}
            )
        ),
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "missing/qualification/approve",
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ]
        },
    )

    assert response.status_code == 404
