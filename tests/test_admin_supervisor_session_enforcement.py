from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from processual_api.routers import settings as settings_routes
from processual_api.supervision_rbac import (
    OPERATIONS_SUPERVISOR,
    REVIEW_SUPERVISOR,
)


def _entry() -> dict:
    return {
        "id": "creq_session_scope",
        "status": "pending",
        "source": "client_settings",
        "created_at": "2026-07-05T09:00:00+00:00",
        "updated_at": "2026-07-05T09:00:00+00:00",
        "user_id": "client-alpha",
        "client_id": "client-alpha",
        "role": "client",
        "request_type": "general_support",
        "request_label": "General support",
        "requested_plan": "enterprise",
        "message": "Please review this account request safely.",
        "status_history": [],
        "supervisor_response_drafts": [
            {
                "draft_id": "rdraft_session_scope",
                "body": "Thanks. We reviewed your request safely.",
                "created_at": "2026-07-05T09:05:00+00:00",
                "updated_at": "2026-07-05T09:05:00+00:00",
                "state": "draft",
                "actor": "reviewer@example.test",
            }
        ],
    }


def _write_file(tmp_path: Path) -> Path:
    path = tmp_path / "settings_client-alpha.json"
    path.write_text(
        json.dumps({"client_requests": [_entry()]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _patch_files(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    monkeypatch.setattr(settings_routes, "_admin_client_request_raw_files", lambda: [path])
    monkeypatch.setattr(
        settings_routes,
        "_admin_client_request_user_id_from_path",
        lambda _path: "client-alpha",
    )


def _review_user() -> dict:
    return {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "reviewer@example.test",
        "supervision_level": REVIEW_SUPERVISOR,
    }


def _ops_user() -> dict:
    return {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "ops@example.test",
        "supervision_level": OPERATIONS_SUPERVISOR,
    }


def test_review_supervisor_can_mark_reviewed_but_cannot_approve(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_file(tmp_path)
    _patch_files(monkeypatch, path)

    reviewed = asyncio.run(
        settings_routes.update_admin_client_request_status(
            "creq_session_scope",
            {"status": "reviewed"},
            current_user=_review_user(),
        )
    )
    assert reviewed["request"]["status"] == "reviewed"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.update_admin_client_request_status(
                "creq_session_scope",
                {"status": "approved"},
                current_user=_review_user(),
            )
        )

    assert exc.value.status_code == 403


def test_review_supervisor_can_save_draft_but_cannot_send_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_file(tmp_path)
    _patch_files(monkeypatch, path)

    draft = asyncio.run(
        settings_routes.save_admin_client_request_response_draft(
            "creq_session_scope",
            {"mode": "generate"},
            current_user=_review_user(),
        )
    )
    assert draft["draft"]["body"]

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            settings_routes.send_admin_client_request_supervisor_response(
                "creq_session_scope",
                {"draft_id": "rdraft_session_scope"},
                current_user=_review_user(),
            )
        )

    assert exc.value.status_code == 403


def test_operations_supervisor_can_decide_and_send_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_file(tmp_path)
    _patch_files(monkeypatch, path)

    approved = asyncio.run(
        settings_routes.update_admin_client_request_status(
            "creq_session_scope",
            {"status": "approved"},
            current_user=_ops_user(),
        )
    )
    assert approved["request"]["status"] == "approved"

    sent = asyncio.run(
        settings_routes.send_admin_client_request_supervisor_response(
            "creq_session_scope",
            {"draft_id": "rdraft_session_scope"},
            current_user=_ops_user(),
        )
    )
    assert sent["status"] == "sent"
    assert sent["supervisor_response"]["event"] == "supervisor_response_sent"


def test_legacy_admin_without_supervision_level_remains_owner_compatible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_file(tmp_path)
    _patch_files(monkeypatch, path)

    legacy_admin = {
        "role": "admin",
        "session_type": "ui_admin",
        "email": "legacy-owner@example.test",
    }

    result = asyncio.run(
        settings_routes.send_admin_client_request_supervisor_response(
            "creq_session_scope",
            {"draft_id": "rdraft_session_scope"},
            current_user=legacy_admin,
        )
    )

    assert result["status"] == "sent"


def test_admin_request_routes_reference_supervision_scope_guards_static() -> None:
    source = Path("processual_api/routers/settings.py").read_text(encoding="utf-8")

    assert "_require_admin_supervision_scope" in source
    assert "_require_admin_client_request_status_supervision_scope" in source
    assert "CLIENTS_STATUS_REVIEW_SCOPE" in source
    assert "CLIENTS_STATUS_DECIDE_SCOPE" in source
    assert "CLIENTS_DRAFT_SCOPE" in source
    assert "CLIENTS_RESPOND_SCOPE" in source
