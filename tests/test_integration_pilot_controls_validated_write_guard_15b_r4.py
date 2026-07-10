from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from processual_api.main import app
from processual_api.supervisor_session_keys import (
    issue_supervisor_session_key,
)


def _helper_module():
    helper_path = Path(
        "tests/test_admin_supervisor_session_keys.py"
    ).resolve()

    spec = importlib.util.spec_from_file_location(
        "pmk_supervisor_session_keys_helpers_15b_r4",
        helper_path,
    )

    if spec is None or spec.loader is None:
        raise AssertionError(
            "Could not load supervisor key helpers"
        )

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _issue_session(
    store: Path,
    *,
    scopes: list[str],
) -> dict[str, object]:
    module = _helper_module()

    issued = issue_supervisor_session_key(
        store,
        dict(module._owner()),
        {
            "label": "15B-R4 pilot controls guard",
            "level": "operations_supervisor",
            "scopes": scopes,
        },
    )

    data = json.loads(
        store.read_text(encoding="utf-8")
    )

    for record in data.get(
        "supervisor_session_keys"
    ) or []:
        if (
            str(record.get("session_key_id") or "")
            == str(
                issued["record"]["session_key_id"]
            )
        ):
            record["scopes"] = list(scopes)

    store.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    issued["record"]["scopes"] = list(scopes)
    return issued


def _configure_paths(
    monkeypatch,
    tmp_path: Path,
) -> dict[str, Path]:
    paths = {
        "task": (
            tmp_path / "integration_pilot_tasks.json"
        ),
        "session": (
            tmp_path / "supervisor_session_keys.json"
        ),
        "audit": (
            tmp_path / "admin_audit_events.jsonl"
        ),
    }

    monkeypatch.setenv(
        "PMK_INTEGRATION_PILOT_TASKS_STORE",
        str(paths["task"]),
    )
    monkeypatch.setenv(
        "PMK_SUPERVISOR_SESSION_KEYS_PATH",
        str(paths["session"]),
    )
    monkeypatch.setenv(
        "PMK_ADMIN_AUDIT_EVENTS_PATH",
        str(paths["audit"]),
    )

    return paths


def _payload() -> dict[str, object]:
    return {
        "client_id": "operator-client-15b-r4",
        "operator_org_id": "operator-org-15b-r4",
        "pilot_terms_note": (
            "Sandbox preparation only."
        ),
    }


def test_r4_fake_canonical_session_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _configure_paths(monkeypatch, tmp_path)

    response = TestClient(app).post(
        "/settings/admin/integration-tasks",
        headers={
            "X-Supervisor-Session-Key": (
                "fake-canonical-session"
            ),
            "X-Admin-Supervisor-Scope": (
                "admin:integration_readiness:write"
            ),
        },
        json=_payload(),
    )

    assert response.status_code == 403

    detail = response.json()["detail"]

    assert (
        detail["error"]
        == "invalid_supervisor_session"
    )
    assert (
        detail["supervisor_session_present"]
        is True
    )
    assert (
        detail["supervisor_session_validated"]
        is False
    )
    assert detail["runtime_enabled"] is False
    assert detail["production_allowed"] is False
    assert detail["external_http_enabled"] is False
    assert detail["raw_secret_visible"] is False


def test_r4_forged_scope_cannot_elevate_session(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _configure_paths(monkeypatch, tmp_path)

    issued = _issue_session(
        paths["session"],
        scopes=["admin:billing:read"],
    )

    response = TestClient(app).post(
        "/settings/admin/integration-tasks",
        headers={
            "X-Admin-Supervisor-Session": str(
                issued["raw_key"]
            ),
            "X-Admin-Supervisor-Scopes": (
                "admin:integration_readiness:write"
            ),
        },
        json=_payload(),
    )

    assert response.status_code == 403

    detail = response.json()["detail"]

    assert (
        detail["error"]
        == "supervisor_scope_required"
    )
    assert (
        detail["supervisor_session_validated"]
        is True
    )
    assert (
        detail["session_key_id"]
        == issued["record"]["session_key_id"]
    )
    assert (
        "admin:billing:read"
        in detail["provided_scopes"]
    )
    assert (
        "admin:integration_readiness:write"
        not in detail["provided_scopes"]
    )


def test_r4_routes_persist_only_safe_actor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = _configure_paths(monkeypatch, tmp_path)

    issued = _issue_session(
        paths["session"],
        scopes=[
            "admin:integration_readiness:write"
        ],
    )

    raw_session = str(issued["raw_key"])
    safe_actor = str(
        issued["record"]["session_key_id"]
    )

    client = TestClient(app)

    created_response = client.post(
        "/settings/admin/integration-tasks",
        headers={
            "X-Supervisor-Session-Key": raw_session,
            "X-Admin-Supervisor-Scope": (
                "admin:billing:read"
            ),
        },
        json=_payload(),
    )

    assert created_response.status_code == 200

    created = created_response.json()
    task_id = str(created["task"]["task_id"])

    assert (
        created["task"]["created_by"]
        == safe_actor
    )
    assert (
        created["task"]["timeline"][0]["actor"]
        == safe_actor
    )
    assert raw_session not in created_response.text

    activation_response = client.post(
        (
            "/settings/admin/integration-tasks/"
            f"{task_id}/activation-permission-key"
        ),
        headers={
            "X-Admin-Supervisor-Session": (
                raw_session
            ),
            "X-Admin-Supervisor-Scope": (
                "admin:billing:read"
            ),
        },
        json={},
    )

    assert activation_response.status_code == 200

    activation = activation_response.json()

    assert (
        activation["task"][
            "activation_permission_issued_by"
        ]
        == safe_actor
    )
    assert (
        activation["task"]["timeline"][-1][
            "actor"
        ]
        == safe_actor
    )
    assert (
        raw_session
        not in activation_response.text
    )

    suspend_response = client.post(
        (
            "/settings/admin/integration-tasks/"
            f"{task_id}/suspend"
        ),
        headers={
            "X-Supervisor-Session-Key": raw_session,
            "X-Admin-Supervisor-Scope": (
                "admin:billing:read"
            ),
        },
        json={"reason": "R4 safe actor proof"},
    )

    assert suspend_response.status_code == 200

    suspended = suspend_response.json()

    assert (
        suspended["task"]["timeline"][-1][
            "actor"
        ]
        == safe_actor
    )
    assert raw_session not in suspend_response.text

    task_text = paths["task"].read_text(
        encoding="utf-8"
    )
    audit_text = paths["audit"].read_text(
        encoding="utf-8"
    )

    assert raw_session not in task_text
    assert raw_session not in audit_text
    assert safe_actor in task_text
    assert safe_actor in audit_text
    assert "integration_task_created" in audit_text
    assert (
        "integration_activation_permission_key_issued"
        in audit_text
    )
    assert (
        "integration_task_suspended"
        in audit_text
    )
