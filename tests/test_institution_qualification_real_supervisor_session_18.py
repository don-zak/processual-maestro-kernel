import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from processual_api.auth.security import get_current_user
from processual_api.main import app
from processual_api.routers import institution_qualification_18
from processual_api.supervision_rbac import (
    OPERATIONS_SUPERVISOR,
    OWNER_SUPERVISOR,
    REVIEW_SUPERVISOR,
)
from processual_api.supervisor_session_keys import (
    issue_supervisor_session_key,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _owner_user() -> dict:
    return {
        "role": "admin",
        "email": "owner@example.test",
        "supervision_level": OWNER_SUPERVISOR,
    }


def _override_admin() -> None:
    def dependency() -> dict:
        return {
            "sub": "admin_demo",
            "email": "admin@example.test",
            "role": "admin",
            "scopes": ["admin:*"],
        }

    app.dependency_overrides[
        get_current_user
    ] = dependency


def _write_case(
    data_dir: Path,
    *,
    case_id: str,
) -> None:
    payload = {
        "institution_integration_cases": [
            {
                "case_id": case_id,
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
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _issue_session(
    store: Path,
    *,
    level: str,
    issued_to: str,
) -> dict:
    return issue_supervisor_session_key(
        store,
        _owner_user(),
        {
            "level": level,
            "issued_to": issued_to,
            "session_label": (
                f"Stage 18 {level} proof"
            ),
            "reason": (
                "Stage 18 qualification "
                "route integration proof."
            ),
        },
    )


def _headers(raw_key: str) -> dict[str, str]:
    return {
        "X-Supervisor-Session-Key": raw_key,
    }


def _configure_paths(
    tmp_path: Path,
    monkeypatch,
) -> tuple[Path, Path]:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    supervisor_store = (
        tmp_path
        / "supervisor_session_keys.json"
    )
    qualification_store = (
        tmp_path
        / "qualification.json"
    )

    monkeypatch.setattr(
        institution_qualification_18,
        "_data_dir",
        lambda: data_dir,
    )

    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(supervisor_store),
    )
    monkeypatch.setenv(
        "PMK_ENTERPRISE_QUALIFICATION_STORE_PATH",
        str(qualification_store),
    )

    _override_admin()

    return data_dir, supervisor_store


def test_review_supervisor_can_request_revision(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir, supervisor_store = (
        _configure_paths(
            tmp_path,
            monkeypatch,
        )
    )

    _write_case(
        data_dir,
        case_id="icase_review",
    )

    issued = _issue_session(
        supervisor_store,
        level=REVIEW_SUPERVISOR,
        issued_to="reviewer@example.test",
    )

    raw_key = str(issued["raw_key"])

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_review/qualification/"
        "request-revision",
        headers=_headers(raw_key),
        json={
            "reason": (
                "Correct the sandbox endpoint "
                "evidence."
            )
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["status"]
        == "revision_required"
    )
    assert payload["production_allowed"] is False
    assert (
        payload["runtime_connector_approved"]
        is False
    )
    assert payload["raw_secret_visible"] is False

    serialized = json.dumps(
        payload,
        sort_keys=True,
    )

    assert raw_key not in serialized
    assert "pmk_sup_" not in serialized
    assert "key_hash" not in serialized


def test_review_supervisor_cannot_approve(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir, supervisor_store = (
        _configure_paths(
            tmp_path,
            monkeypatch,
        )
    )

    _write_case(
        data_dir,
        case_id="icase_review_denied",
    )

    issued = _issue_session(
        supervisor_store,
        level=REVIEW_SUPERVISOR,
        issued_to="reviewer@example.test",
    )

    raw_key = str(issued["raw_key"])

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_review_denied/qualification/"
        "approve",
        headers=_headers(raw_key),
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ],
            "reason": (
                "Attempted approval by review role."
            ),
        },
    )

    assert response.status_code == 403

    serialized = response.text

    assert raw_key not in serialized
    assert "pmk_sup_" not in serialized

    assert not (
        tmp_path / "qualification.json"
    ).exists()


def test_operations_supervisor_can_approve(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir, supervisor_store = (
        _configure_paths(
            tmp_path,
            monkeypatch,
        )
    )

    _write_case(
        data_dir,
        case_id="icase_ops",
    )

    issued = _issue_session(
        supervisor_store,
        level=OPERATIONS_SUPERVISOR,
        issued_to="operations@example.test",
    )

    raw_key = str(issued["raw_key"])
    session_key_id = str(
        issued["record"]["session_key_id"]
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_ops/qualification/approve",
        headers=_headers(raw_key),
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
        == "icase_ops"
    )
    assert (
        payload["grant"]["client_id"]
        == "client_demo"
    )

    assert (
        "supervisor_session_key_id"
        not in payload["grant"]
    )

    serialized = json.dumps(
        payload,
        sort_keys=True,
    )

    assert raw_key not in serialized
    assert session_key_id not in serialized
    assert "pmk_sup_" not in serialized
    assert "key_hash" not in serialized
    assert "raw_key" not in serialized

    assert payload["production_allowed"] is False
    assert (
        payload["runtime_connector_approved"]
        is False
    )
    assert payload["raw_secret_visible"] is False

    qualification_store = (
        tmp_path / "qualification.json"
    )

    persisted = qualification_store.read_text(
        encoding="utf-8"
    )

    assert raw_key not in persisted
    assert "pmk_sup_" not in persisted

    stored_json = json.loads(persisted)

    assert (
        stored_json["grants"][0][
            "supervisor_session_key_id"
        ]
        == session_key_id
    )


def test_missing_supervisor_session_is_denied(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir, _supervisor_store = (
        _configure_paths(
            tmp_path,
            monkeypatch,
        )
    )

    _write_case(
        data_dir,
        case_id="icase_missing_session",
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_missing_session/qualification/"
        "approve",
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ]
        },
    )

    assert response.status_code == 403

    assert not (
        tmp_path / "qualification.json"
    ).exists()


def test_invalid_supervisor_session_is_denied(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir, _supervisor_store = (
        _configure_paths(
            tmp_path,
            monkeypatch,
        )
    )

    _write_case(
        data_dir,
        case_id="icase_invalid_session",
    )

    invalid_raw_key = (
        "pmk_sup_invalid_stage18_value"
    )

    response = client.post(
        "/settings/admin/integration-cases/"
        "icase_invalid_session/qualification/"
        "approve",
        headers=_headers(invalid_raw_key),
        json={
            "approved_task_ids": [
                "sandbox_capability_probe"
            ]
        },
    )

    assert response.status_code == 403
    assert invalid_raw_key not in response.text

    assert not (
        tmp_path / "qualification.json"
    ).exists()
