"""Stage 18 institution qualification read routes.

These routes expose safe qualification and task-binding projections only.
They do not issue, redeem, rotate, suspend, or revoke credentials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from pydantic import BaseModel, Field

from processual_api.auth.security import get_current_user
from processual_api.services.enterprise_qualification_decisions_18 import (
    QualificationDecisionError,
    activate_enterprise_qualification,
    approve_sandbox_qualification,
    list_safe_qualification_grants,
    qualification_review_summary,
    request_qualification_revision,
)
from processual_api.services.enterprise_r10_binding_creation_18 import (
    EnterpriseR10BindingCreationError,
    create_enterprise_r10_binding,
)
from processual_api.services.enterprise_r10_binding_store_18 import (
    list_safe_enterprise_r10_bindings,
)
from processual_api.services.enterprise_r10_controlled_sandbox_18 import (
    EnterpriseR10ControlledSandboxError,
    qualify_enterprise_r10_controlled_sandbox,
)
from processual_api.services.enterprise_r10_lifecycle_sync_18 import (
    EnterpriseR10LifecycleSyncError,
    synchronize_enterprise_r10_binding,
)
from processual_api.services.institution_case_admin_index_18 import (
    InstitutionCaseAdminIndexError,
    qualification_review_queue,
    resolve_institution_case,
    safe_institution_case_summary,
)
from processual_api.services.supervisor_session_write_guard import (
    SupervisorSessionWriteGuardError,
    require_validated_supervisor_write_session,
)
from processual_api.supervision_rbac import (
    QUALIFICATION_APPROVE_SCOPE,
    QUALIFICATION_REVIEW_SCOPE,
)

router = APIRouter(
    prefix="/settings",
    tags=["institution-qualification-18"],
)



class QualificationApproveRequest(BaseModel):
    approved_task_ids: list[str] = Field(
        min_length=1,
        max_length=20,
    )
    reason: str = Field(
        default="",
        max_length=1000,
    )
    ttl_days: int = Field(
        default=7,
        ge=1,
        le=30,
    )


class QualificationRevisionRequest(BaseModel):
    reason: str = Field(
        min_length=1,
        max_length=1000,
    )



class EnterpriseR10BindingCreateRequest(BaseModel):
    external_connectivity_case_id: str = Field(
        min_length=1,
        max_length=240,
    )


def _supervisor_actor(
    current_user: dict[str, Any],
) -> str:
    actor = str(
        current_user.get("email")
        or current_user.get("user_id")
        or current_user.get("sub")
        or current_user.get("role")
        or "supervisor"
    ).strip()

    return actor or "supervisor"


def _require_qualification_write_session(
    request: Request,
    *,
    required_scope: str,
) -> dict[str, Any]:
    try:
        return require_validated_supervisor_write_session(
            request,
            {required_scope},
            guard_name=(
                "stage18_enterprise_qualification"
            ),
        )
    except SupervisorSessionWriteGuardError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


def _resolve_admin_case_or_http_error(
    case_id: str,
) -> tuple[str, dict[str, Any]]:
    try:
        return resolve_institution_case(
            data_dir=_data_dir(),
            case_id=case_id,
        )
    except InstitutionCaseAdminIndexError as exc:
        if str(exc) == (
            "institution_case_identity_conflict"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        ) from exc


def _qualification_decision_http_error(
    exc: QualificationDecisionError,
) -> HTTPException:
    message = str(exc)

    if "active qualification grant" in message:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        )

    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    )



_ADMIN_READ_SCOPES = {
    "admin:*",
    "admin:integration:qualification:read",
    "admin:integration:qualification:review",
    "admin:integration_readiness:review",
    "admin:clients:review",
}


def _data_dir() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "data"
    )


def _normalized_scopes(
    current_user: dict[str, Any],
) -> set[str]:
    raw = (
        current_user.get("scopes")
        or current_user.get("permissions")
        or []
    )

    if isinstance(raw, str):
        raw = [raw]

    if not isinstance(
        raw,
        (list, tuple, set),
    ):
        return set()

    return {
        str(scope).strip()
        for scope in raw
        if str(scope or "").strip()
    }


def _require_admin_read(
    current_user: dict[str, Any],
) -> None:
    scopes = _normalized_scopes(
        current_user
    )

    role = str(
        current_user.get("role") or ""
    ).strip().lower()

    if (
        "*" in scopes
        or scopes.intersection(
            _ADMIN_READ_SCOPES
        )
    ):
        return

    if role == "admin" and "admin" in scopes:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Admin qualification read access "
            "is required."
        ),
    )


def _current_identity(
    current_user: dict[str, Any],
) -> tuple[str, str]:
    user_id = str(
        current_user.get("user_id")
        or current_user.get("sub")
        or ""
    ).strip()

    client_id = str(
        current_user.get("client_id")
        or user_id
    ).strip()

    if not user_id or not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated client identity required.",
        )

    return user_id, client_id


def _safe_case_detail(
    *,
    owner_user_id: str,
    case: dict[str, Any],
) -> dict[str, Any]:
    summary = safe_institution_case_summary(
        case,
        owner_user_id=owner_user_id,
    )

    review = qualification_review_summary(
        case
    )

    grants = list_safe_qualification_grants(
        client_id=summary["client_id"],
        case_id=summary["case_id"],
    )

    bindings = list_safe_enterprise_r10_bindings(
        client_id=summary["client_id"],
        institution_case_id=summary[
            "case_id"
        ],
    )

    return {
        "status": "ready",
        "case": summary,
        "qualification_review": review,
        "qualification_grants": grants,
        "task_bindings": bindings,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }


@router.get(
    "/admin/integration-cases/qualification-queue"
)
def admin_qualification_queue_18(
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    _require_admin_read(current_user)

    return qualification_review_queue(
        data_dir=_data_dir()
    )


@router.get(
    "/admin/integration-cases/{case_id}/qualification"
)
def admin_qualification_detail_18(
    case_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    _require_admin_read(current_user)

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        if str(exc) == (
            "institution_case_identity_conflict"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution integration case not found.",
        ) from exc

    return _safe_case_detail(
        owner_user_id=owner_user_id,
        case=case,
    )


@router.get(
    "/client/integration-cases/{case_id}/qualification"
)
def client_qualification_detail_18(
    case_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    user_id, client_id = _current_identity(
        current_user
    )

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution integration case not found.",
        ) from exc

    case_client_id = str(
        case.get("client_id") or ""
    ).strip()

    if (
        owner_user_id != user_id
        or case_client_id != client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution integration case not found.",
        )

    return _safe_case_detail(
        owner_user_id=owner_user_id,
        case=case,
    )


@router.post(
    "/client/integration-cases/"
    "{case_id}/qualification/activate"
)
def activate_client_qualification_18(
    case_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    user_id, client_id = _current_identity(
        current_user
    )

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        ) from exc

    case_client_id = str(
        case.get("client_id") or ""
    ).strip()

    if (
        owner_user_id != user_id
        or case_client_id != client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        )

    try:
        result = activate_enterprise_qualification(
            case=case,
            client_id=client_id,
        )
    except QualificationDecisionError as exc:
        raise (
            _qualification_decision_http_error(
                exc
            )
        ) from exc

    return {
        **result,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }


@router.post(
    "/client/integration-cases/"
    "{case_id}/tasks/{task_id}/r10-binding",
    status_code=status.HTTP_201_CREATED,
)
def create_client_r10_binding_18(
    case_id: str,
    task_id: str,
    payload: EnterpriseR10BindingCreateRequest,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    user_id, client_id = _current_identity(
        current_user
    )

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        ) from exc

    case_client_id = str(
        case.get("client_id") or ""
    ).strip()

    if (
        owner_user_id != user_id
        or case_client_id != client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        )

    try:
        result = create_enterprise_r10_binding(
            institution_case=case,
            institution_task_id=task_id,
            client_id=client_id,
            external_connectivity_case_id=(
                payload.external_connectivity_case_id
            ),
            actor=client_id,
        )
    except EnterpriseR10BindingCreationError as exc:
        detail = str(exc)

        if detail in {
            "activated_qualification_grant_not_found",
            "external_connectivity_case_not_found",
        }:
            response_status = (
                status.HTTP_404_NOT_FOUND
            )
        elif detail in {
            "multiple_activated_qualification_grants",
            "active_task_binding_already_exists",
        }:
            response_status = status.HTTP_409_CONFLICT
        else:
            response_status = (
                status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        raise HTTPException(
            status_code=response_status,
            detail=detail,
        ) from exc

    return {
        **result,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }


@router.post(
    "/client/integration-cases/"
    "{case_id}/tasks/{task_id}/r10-binding/"
    "{binding_id}/controlled-sandbox-qualification"
)
def qualify_client_controlled_sandbox_18(
    case_id: str,
    task_id: str,
    binding_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    user_id, client_id = _current_identity(
        current_user
    )

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        ) from exc

    case_client_id = str(
        case.get("client_id") or ""
    ).strip()

    if (
        owner_user_id != user_id
        or case_client_id != client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        )

    try:
        result = (
            qualify_enterprise_r10_controlled_sandbox(
                binding_id,
                client_id=client_id,
                institution_case_id=case_id,
                institution_task_id=task_id,
            )
        )
    except EnterpriseR10ControlledSandboxError as exc:
        detail = str(exc)

        if detail in {
            "enterprise_r10_binding_not_found",
            "binding_client_mismatch",
            "binding_institution_case_mismatch",
            "binding_institution_task_mismatch",
        }:
            response_status = status.HTTP_404_NOT_FOUND
        elif detail in {
            "binding_not_sandbox_api_key_issued",
            "sandbox_api_key_reference_missing",
        }:
            response_status = status.HTTP_409_CONFLICT
        else:
            response_status = (
                status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        raise HTTPException(
            status_code=response_status,
            detail=detail,
        ) from exc

    return {
        **result,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }


@router.post(
    "/client/integration-cases/"
    "{case_id}/tasks/{task_id}/r10-binding/"
    "{binding_id}/sync"
)
def synchronize_client_r10_binding_18(
    case_id: str,
    task_id: str,
    binding_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    user_id, client_id = _current_identity(
        current_user
    )

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        ) from exc

    case_client_id = str(
        case.get("client_id") or ""
    ).strip()

    if (
        owner_user_id != user_id
        or case_client_id != client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Institution integration case "
                "not found."
            ),
        )

    try:
        result = synchronize_enterprise_r10_binding(
            binding_id,
            client_id=client_id,
            institution_case_id=case_id,
            institution_task_id=task_id,
            actor=client_id,
        )
    except EnterpriseR10LifecycleSyncError as exc:
        detail = str(exc)

        if detail in {
            "enterprise_r10_binding_not_found",
            "external_connectivity_case_not_found",
        }:
            response_status = (
                status.HTTP_404_NOT_FOUND
            )
        elif detail in {
            "binding_client_mismatch",
            "binding_institution_case_mismatch",
            "binding_institution_task_mismatch",
            "external_case_client_mismatch",
            "external_case_task_mismatch",
        }:
            response_status = (
                status.HTTP_404_NOT_FOUND
            )
        elif detail in {
            "qualification_key_reference_missing",
            "sandbox_api_key_reference_missing",
            "external_case_state_not_synchronizable",
        }:
            response_status = (
                status.HTTP_409_CONFLICT
            )
        else:
            response_status = (
                status.HTTP_422_UNPROCESSABLE_CONTENT
            )

        raise HTTPException(
            status_code=response_status,
            detail=detail,
        ) from exc

    return {
        **result,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "write_allowed": False,
        "restricted_allowed": False,
        "raw_secret_visible": False,
    }


@router.get(
    "/client/integration-cases/{case_id}/task-credentials"
)
def client_task_credentials_18(
    case_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    user_id, client_id = _current_identity(
        current_user
    )

    try:
        owner_user_id, case = (
            resolve_institution_case(
                data_dir=_data_dir(),
                case_id=case_id,
            )
        )
    except InstitutionCaseAdminIndexError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution integration case not found.",
        ) from exc

    case_client_id = str(
        case.get("client_id") or ""
    ).strip()

    if (
        owner_user_id != user_id
        or case_client_id != client_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Institution integration case not found.",
        )

    bindings = list_safe_enterprise_r10_bindings(
        client_id=client_id,
        institution_case_id=case_id,
    )

    return {
        "status": "ready",
        "case_id": case_id,
        "client_id": client_id,
        "credential_count": len(bindings),
        "task_credentials": bindings,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }

@router.post(
    "/admin/integration-cases/"
    "{case_id}/qualification/approve",
    status_code=status.HTTP_201_CREATED,
)
def approve_institution_qualification_18(
    case_id: str,
    payload: QualificationApproveRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    _require_admin_read(current_user)

    session = (
        _require_qualification_write_session(
            request,
            required_scope=(
                QUALIFICATION_APPROVE_SCOPE
            ),
        )
    )

    _owner_user_id, case = (
        _resolve_admin_case_or_http_error(
            case_id
        )
    )

    approved_task_ids = tuple(
        dict.fromkeys(
            str(task_id or "").strip()
            for task_id
            in payload.approved_task_ids
            if str(task_id or "").strip()
        )
    )

    try:
        result = approve_sandbox_qualification(
            case=case,
            supervisor_id=(
                _supervisor_actor(
                    current_user
                )
            ),
            supervisor_session_key_id=str(
                session.get("session_key_id")
                or ""
            ),
            approved_task_ids=(
                approved_task_ids
            ),
            reason=payload.reason.strip(),
            ttl_days=payload.ttl_days,
        )
    except QualificationDecisionError as exc:
        raise (
            _qualification_decision_http_error(
                exc
            )
        ) from exc

    return {
        **result,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }


@router.post(
    "/admin/integration-cases/"
    "{case_id}/qualification/"
    "request-revision"
)
def request_institution_qualification_revision_18(
    case_id: str,
    payload: QualificationRevisionRequest,
    request: Request,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    _require_admin_read(current_user)

    session = (
        _require_qualification_write_session(
            request,
            required_scope=(
                QUALIFICATION_REVIEW_SCOPE
            ),
        )
    )

    _owner_user_id, case = (
        _resolve_admin_case_or_http_error(
            case_id
        )
    )

    try:
        result = request_qualification_revision(
            case=case,
            supervisor_id=(
                _supervisor_actor(
                    current_user
                )
            ),
            supervisor_session_key_id=str(
                session.get("session_key_id")
                or ""
            ),
            reason=payload.reason.strip(),
        )
    except QualificationDecisionError as exc:
        raise (
            _qualification_decision_http_error(
                exc
            )
        ) from exc

    return {
        **result,
        "production_allowed": False,
        "runtime_connector_approved": False,
        "external_http_allowed": False,
        "raw_secret_visible": False,
    }
