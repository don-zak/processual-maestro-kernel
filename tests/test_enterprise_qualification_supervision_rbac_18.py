from processual_api.supervision_rbac import (
    OPERATIONS_SUPERVISOR,
    OWNER_SUPERVISOR,
    QUALIFICATION_APPROVE_SCOPE,
    QUALIFICATION_READ_SCOPE,
    QUALIFICATION_REVIEW_SCOPE,
    REVIEW_SUPERVISOR,
    can_use_supervision_scope,
    safe_supervision_permission_matrix,
    scopes_for_supervision_level,
)


def test_owner_supervisor_has_full_qualification_authority() -> None:
    scopes = scopes_for_supervision_level(
        OWNER_SUPERVISOR
    )

    assert QUALIFICATION_READ_SCOPE in scopes
    assert QUALIFICATION_REVIEW_SCOPE in scopes
    assert QUALIFICATION_APPROVE_SCOPE in scopes


def test_operations_supervisor_can_approve_qualification() -> None:
    scopes = scopes_for_supervision_level(
        OPERATIONS_SUPERVISOR
    )

    assert QUALIFICATION_READ_SCOPE in scopes
    assert QUALIFICATION_REVIEW_SCOPE in scopes
    assert QUALIFICATION_APPROVE_SCOPE in scopes


def test_review_supervisor_can_review_but_not_approve() -> None:
    scopes = scopes_for_supervision_level(
        REVIEW_SUPERVISOR
    )

    assert QUALIFICATION_READ_SCOPE in scopes
    assert QUALIFICATION_REVIEW_SCOPE in scopes
    assert QUALIFICATION_APPROVE_SCOPE not in scopes


def test_qualification_scopes_are_reflected_by_permission_matrix() -> None:
    matrix = safe_supervision_permission_matrix()

    assert (
        QUALIFICATION_APPROVE_SCOPE
        in matrix[OWNER_SUPERVISOR]
    )
    assert (
        QUALIFICATION_APPROVE_SCOPE
        in matrix[OPERATIONS_SUPERVISOR]
    )
    assert (
        QUALIFICATION_APPROVE_SCOPE
        not in matrix[REVIEW_SUPERVISOR]
    )


def test_explicit_qualification_scope_is_supported() -> None:
    user = {
        "supervision_level": REVIEW_SUPERVISOR,
        "supervision_scopes": [
            QUALIFICATION_APPROVE_SCOPE
        ],
    }

    assert can_use_supervision_scope(
        user,
        QUALIFICATION_APPROVE_SCOPE,
    )
