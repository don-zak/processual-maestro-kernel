from __future__ import annotations

import pytest

from processual_api.supervision_rbac import (
    OPERATIONS_SUPERVISOR,
    OWNER_SUPERVISOR,
    REVIEW_SUPERVISOR,
    SUPERVISION_LEVELS,
    can_issue_supervisor_session_key,
    can_use_supervision_scope,
    require_supervision_scope,
    safe_supervision_permission_matrix,
    scopes_for_supervision_level,
)


def test_supervision_levels_are_fixed_to_three_roles() -> None:
    assert SUPERVISION_LEVELS == (
        OWNER_SUPERVISOR,
        OPERATIONS_SUPERVISOR,
        REVIEW_SUPERVISOR,
    )


def test_owner_supervisor_is_only_level_that_can_issue_session_keys() -> None:
    assert can_issue_supervisor_session_key(OWNER_SUPERVISOR) is True
    assert can_issue_supervisor_session_key(OPERATIONS_SUPERVISOR) is False
    assert can_issue_supervisor_session_key(REVIEW_SUPERVISOR) is False
    assert can_issue_supervisor_session_key("admin") is False
    assert can_issue_supervisor_session_key("") is False


def test_operations_supervisor_can_execute_client_request_workflow_but_not_issue_keys() -> None:
    scopes = scopes_for_supervision_level(OPERATIONS_SUPERVISOR)

    assert "admin:clients:read" in scopes
    assert "admin:clients:context" in scopes
    assert "admin:clients:status_review" in scopes
    assert "admin:clients:status_decide" in scopes
    assert "admin:clients:draft" in scopes
    assert "admin:clients:respond" in scopes
    assert "admin:usage:read" in scopes
    assert "admin:quota:read" in scopes

    assert "admin:supervisor_sessions:issue" not in scopes
    assert "admin:supervisor_sessions:revoke" not in scopes
    assert "admin:api_keys:write" not in scopes
    assert "admin:providers:write" not in scopes
    assert "admin:rbac:write" not in scopes


def test_review_supervisor_can_review_and_draft_but_cannot_send_or_decide() -> None:
    scopes = scopes_for_supervision_level(REVIEW_SUPERVISOR)

    assert "admin:clients:read" in scopes
    assert "admin:clients:context" in scopes
    assert "admin:clients:status_review" in scopes
    assert "admin:clients:draft" in scopes

    assert "admin:clients:respond" not in scopes
    assert "admin:clients:status_decide" not in scopes
    assert "admin:quota:write" not in scopes
    assert "admin:api_keys:write" not in scopes
    assert "admin:supervisor_sessions:issue" not in scopes


def test_scope_check_accepts_level_or_explicit_scope() -> None:
    user = {
        "supervision_level": REVIEW_SUPERVISOR,
        "supervision_scopes": ["admin:audit:read"],
    }

    assert can_use_supervision_scope(user, "admin:clients:read") is True
    assert can_use_supervision_scope(user, "admin:audit:read") is True
    assert can_use_supervision_scope(user, "admin:clients:respond") is False


def test_require_supervision_scope_raises_permission_error_for_missing_scope() -> None:
    user = {"supervision_level": REVIEW_SUPERVISOR}

    require_supervision_scope(user, "admin:clients:read")

    with pytest.raises(PermissionError):
        require_supervision_scope(user, "admin:clients:respond")


def test_safe_permission_matrix_contains_no_secret_markers() -> None:
    matrix = safe_supervision_permission_matrix()
    rendered = repr(matrix).lower()

    assert OWNER_SUPERVISOR in matrix
    assert OPERATIONS_SUPERVISOR in matrix
    assert REVIEW_SUPERVISOR in matrix

    forbidden = (
        "raw key",
        "provider_secret",
        "encrypted_key",
        "authorization",
        "cookie",
        "jwt",
    )
    for marker in forbidden:
        assert marker not in rendered
