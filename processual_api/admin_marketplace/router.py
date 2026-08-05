from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from processual_api.admin_marketplace.eligibility_service import (
    AdminMarketplaceEligibilityState,
)
from processual_api.admin_marketplace.errors import (
    AdminMarketplaceAuthorityDeniedError,
    AdminMarketplaceError,
    AdminMarketplaceStepUpRequiredError,
    PaymentDestinationConflictError,
    PaymentDestinationNotFoundError,
    PaymentEvidenceNotFoundError,
    PaymentVerificationConflictError,
)
from processual_api.admin_marketplace.payment_destination_contracts import (
    PaymentDestinationCreateContract,
    PaymentDestinationStatus,
    PaymentDestinationType,
)
from processual_api.admin_marketplace.payment_destination_service import (
    PaymentDestinationAdministrationResult,
    PaymentDestinationAdministrationService,
)
from processual_api.admin_marketplace.payment_evidence_service import (
    AdminPaymentVerificationResult,
)
from processual_api.admin_marketplace.persistence.errors import (
    AdminMarketplaceConflictError,
    AdminMarketplacePersistenceError,
)
from processual_api.admin_marketplace.runtime import (
    AdminMarketplaceRuntime,
    AdminMarketplaceRuntimeUnavailableError,
    build_admin_marketplace_runtime,
)
from processual_api.auth.session_router import get_identity_user

GENERIC_UNAVAILABLE = "Admin Marketplace is temporarily unavailable."
MAX_ADMIN_MARKETPLACE_REQUEST_BYTES = 16 * 1024


class SensitiveAdminMarketplaceAPIRoute(APIRoute):
    def get_route_handler(self):
        route_handler = super().get_route_handler()

        async def sanitized_route_handler(request: Request):
            if request.method in {"POST", "PUT", "PATCH"}:
                content_type = request.headers.get("content-type", "")
                media_type = content_type.split(";", 1)[0].strip().lower()
                if media_type != "application/json":
                    return JSONResponse(
                        status_code=415,
                        content={"detail": "Admin Marketplace requests require JSON."},
                    )
                content_length = request.headers.get("content-length")
                try:
                    declared_length = int(content_length) if content_length is not None else 0
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Admin Marketplace request."},
                    )
                if declared_length > MAX_ADMIN_MARKETPLACE_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Admin Marketplace request is too large."},
                    )
                if len(await request.body()) > MAX_ADMIN_MARKETPLACE_REQUEST_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Admin Marketplace request is too large."},
                    )
            try:
                return await route_handler(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={"detail": "Invalid Admin Marketplace request."},
                )

        return sanitized_route_handler


router = APIRouter(
    prefix="/admin-marketplace",
    tags=["admin-marketplace"],
    route_class=SensitiveAdminMarketplaceAPIRoute,
)


class AdminMarketplaceEligibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_ref: str
    state: AdminMarketplaceEligibilityState
    visible: bool
    country_code: str | None
    address_status: str | None
    maestro_direct_status: str | None
    admin_review_required: bool
    reason_code: str


class PaymentDestinationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    destination_ref: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=2, max_length=120)
    destination_type: PaymentDestinationType
    institution_name: str = Field(min_length=1, max_length=160)
    account_holder_name: str = Field(min_length=1, max_length=160)
    raw_account_identifier: SecretStr
    instructions: str | None = Field(default=None, max_length=1000)


class PaymentDestinationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    destination_id: str
    destination_ref: str
    display_name: str
    destination_type: str
    institution_name: str
    account_holder_name: str
    masked_identifier: str
    country_code: str
    currency: str
    sales_channel: str
    status: PaymentDestinationStatus
    validation_method: str | None
    validation_reason_code: str | None
    validated_at: datetime | None
    is_active: bool
    is_default: bool
    effective_at: datetime | None
    expires_at: datetime | None
    instructions: str | None
    created_at: datetime
    updated_at: datetime
    reason_code: str


class PaymentDestinationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[PaymentDestinationResponse, ...]
    count: int


class CommercialOrderReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_ref: str
    customer_ref: str
    plan_ref: str
    offer_ref: str
    billing_period: str
    status: str
    contract_status: str
    payment_status: str
    payment_reference: str | None
    total_amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime


class CommercialOrderListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CommercialOrderReadResponse, ...]
    count: int


class CommercialContractReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_ref: str
    order_ref: str
    customer_ref: str
    contract_version: str
    status: str
    acceptance_method: str
    evidence_reference: str
    completed_at: datetime


class CommercialContractListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[CommercialContractReadResponse, ...]
    count: int


class PaymentEvidenceReadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_ref: str
    order_ref: str
    customer_ref: str
    source_type: str
    status: str
    actual_amount: Decimal
    currency: str
    safe_source_reference: str
    reference_matched: bool
    amount_matched: bool
    currency_matched: bool
    destination_matched: bool
    match_reason_code: str
    reported_at: datetime


class PaymentEvidenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[PaymentEvidenceReadResponse, ...]
    count: int


class PaymentVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: str = Field(pattern="^(verified|rejected)$")
    reason_code: str = Field(min_length=2, max_length=128)


class PaymentVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str
    verification_ref: str
    evidence_ref: str
    order_ref: str
    status: str
    decision_reason_code: str
    decided_at: datetime
    order_status: str
    payment_status: str
    reason_code: str


async def get_admin_marketplace_runtime() -> AdminMarketplaceRuntime:
    try:
        return await build_admin_marketplace_runtime()
    except AdminMarketplaceRuntimeUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc


def _identity_principal(current_user: dict) -> tuple[str, str]:
    try:
        user_id = str(current_user["user_id"]).strip()
        session_id = str(current_user["session_id"]).strip()
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        ) from exc

    if not user_id or not session_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        )

    return user_id, session_id


@router.get(
    "/eligibility/{customer_ref}",
    response_model=AdminMarketplaceEligibilityResponse,
)
async def get_admin_marketplace_eligibility(
    customer_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
) -> AdminMarketplaceEligibilityResponse:
    user_id, session_id = _identity_principal(current_user)

    try:
        authority = await runtime.authority_resolver.resolve(
            user_id=user_id,
            session_id=session_id,
        )
        result = await runtime.eligibility_service.evaluate(
            authority=authority,
            customer_ref=customer_ref,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid Admin Marketplace eligibility request.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        ) from exc

    return AdminMarketplaceEligibilityResponse(
        customer_ref=result.customer_ref,
        state=result.state,
        visible=result.visible,
        country_code=result.country_code,
        address_status=result.address_status,
        maestro_direct_status=result.maestro_direct_status,
        admin_review_required=result.admin_review_required,
        reason_code=result.reason_code,
    )


async def _commercial_read_authority(*, current_user: dict, runtime):
    user_id, session_id = _identity_principal(current_user)
    return await runtime.authority_resolver.resolve(
        user_id=user_id,
        session_id=session_id,
    )


@router.get("/orders", response_model=CommercialOrderListResponse)
async def list_admin_marketplace_orders(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> CommercialOrderListResponse:
    try:
        authority = await _commercial_read_authority(
            current_user=current_user,
            runtime=runtime,
        )
        items = await runtime.commercial_read_service.list_orders(
            authority=authority,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    responses = tuple(CommercialOrderReadResponse.model_validate(item, from_attributes=True) for item in items)
    return CommercialOrderListResponse(items=responses, count=len(responses))


@router.get("/contracts", response_model=CommercialContractListResponse)
async def list_admin_marketplace_contracts(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> CommercialContractListResponse:
    try:
        authority = await _commercial_read_authority(
            current_user=current_user,
            runtime=runtime,
        )
        items = await runtime.commercial_read_service.list_contracts(
            authority=authority,
        )
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    responses = tuple(CommercialContractReadResponse.model_validate(item, from_attributes=True) for item in items)
    return CommercialContractListResponse(items=responses, count=len(responses))


@router.get("/payment-evidence", response_model=PaymentEvidenceListResponse)
async def list_admin_marketplace_payment_evidence(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
) -> PaymentEvidenceListResponse:
    try:
        authority = await _commercial_read_authority(current_user=current_user, runtime=runtime)
        items = await runtime.commercial_read_service.list_payment_evidence(authority=authority)
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    responses = tuple(PaymentEvidenceReadResponse.model_validate(item, from_attributes=True) for item in items)
    return PaymentEvidenceListResponse(items=responses, count=len(responses))


def _payment_verification_response(
    result: AdminPaymentVerificationResult,
) -> PaymentVerificationResponse:
    return PaymentVerificationResponse(
        verification_id=str(result.verification_id),
        verification_ref=result.verification_ref,
        evidence_ref=result.evidence_ref,
        order_ref=result.order_ref,
        status=result.status,
        decision_reason_code=result.decision_reason_code,
        decided_at=result.decided_at,
        order_status=result.order_status,
        payment_status=result.payment_status,
        reason_code=result.reason_code,
    )


@router.post(
    "/payment-evidence/{evidence_ref}/verify",
    response_model=PaymentVerificationResponse,
)
async def verify_admin_marketplace_payment(
    evidence_ref: str,
    body: PaymentVerificationRequest,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(get_admin_marketplace_runtime),
    correlation_id: str = Header(..., alias="X-Correlation-ID", min_length=1, max_length=128),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=16, max_length=128),
) -> PaymentVerificationResponse:
    try:
        authority = await _commercial_read_authority(current_user=current_user, runtime=runtime)
        result = await runtime.payment_verification_service.decide(
            authority=authority,
            evidence_ref=evidence_ref,
            decision=body.decision,
            reason_code=body.reason_code,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
    except AdminMarketplaceStepUpRequiredError as exc:
        raise HTTPException(status_code=428, detail="Recent MFA step-up is required.") from exc
    except AdminMarketplaceAuthorityDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        ) from exc
    except PaymentEvidenceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Payment evidence was not found.") from exc
    except (PaymentVerificationConflictError, AdminMarketplaceConflictError) as exc:
        raise HTTPException(
            status_code=409,
            detail="Payment verification conflicts with stored state.",
        ) from exc
    except AdminMarketplaceError as exc:
        raise HTTPException(status_code=400, detail="Invalid payment verification request.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=GENERIC_UNAVAILABLE) from exc
    return _payment_verification_response(result)


def _payment_destination_service(
    runtime: AdminMarketplaceRuntime,
) -> PaymentDestinationAdministrationService:
    service = runtime.payment_destination_service
    if service is None:
        raise HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        )
    return service


async def _payment_destination_authority(
    *,
    current_user: dict,
    runtime: AdminMarketplaceRuntime,
):
    user_id, session_id = _identity_principal(current_user)
    return await runtime.authority_resolver.resolve(
        user_id=user_id,
        session_id=session_id,
    )


def _payment_destination_command(
    body: PaymentDestinationCreateRequest,
) -> PaymentDestinationCreateContract:
    return PaymentDestinationCreateContract(
        destination_ref=body.destination_ref,
        display_name=body.display_name,
        destination_type=body.destination_type,
        institution_name=body.institution_name,
        account_holder_name=body.account_holder_name,
        raw_account_identifier=(body.raw_account_identifier.get_secret_value()),
        instructions=body.instructions,
    )


def _payment_destination_response(
    result: PaymentDestinationAdministrationResult,
) -> PaymentDestinationResponse:
    return PaymentDestinationResponse(
        destination_id=str(result.destination_id),
        destination_ref=result.destination_ref,
        display_name=result.display_name,
        destination_type=result.destination_type,
        institution_name=result.institution_name,
        account_holder_name=result.account_holder_name,
        masked_identifier=result.masked_identifier,
        country_code=result.country_code,
        currency=result.currency,
        sales_channel=result.sales_channel,
        status=result.status,
        validation_method=result.validation_method,
        validation_reason_code=result.validation_reason_code,
        validated_at=result.validated_at,
        is_active=result.is_active,
        is_default=result.is_default,
        effective_at=result.effective_at,
        expires_at=result.expires_at,
        instructions=result.instructions,
        created_at=result.created_at,
        updated_at=result.updated_at,
        reason_code=result.reason_code,
    )


def _payment_destination_http_exception(
    exc: Exception,
) -> HTTPException:
    if isinstance(exc, AdminMarketplaceStepUpRequiredError):
        return HTTPException(
            status_code=428,
            detail="Recent MFA step-up is required.",
        )
    if isinstance(exc, AdminMarketplaceAuthorityDeniedError):
        return HTTPException(
            status_code=403,
            detail="Active platform administrator authority is required.",
        )
    if isinstance(exc, PaymentDestinationNotFoundError):
        return HTTPException(
            status_code=404,
            detail="Payment destination was not found.",
        )
    if isinstance(
        exc,
        (PaymentDestinationConflictError, AdminMarketplaceConflictError),
    ):
        return HTTPException(
            status_code=409,
            detail="Payment destination request conflicts with stored state.",
        )
    if isinstance(exc, AdminMarketplaceError):
        return HTTPException(
            status_code=400,
            detail="Invalid payment destination request.",
        )
    if isinstance(exc, AdminMarketplacePersistenceError):
        return HTTPException(
            status_code=503,
            detail=GENERIC_UNAVAILABLE,
        )
    return HTTPException(
        status_code=503,
        detail=GENERIC_UNAVAILABLE,
    )


@router.post(
    "/payment-destinations",
    response_model=PaymentDestinationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_destination(
    body: PaymentDestinationCreateRequest,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
    ),
) -> PaymentDestinationResponse:
    try:
        service = _payment_destination_service(runtime)
        authority = await _payment_destination_authority(
            current_user=current_user,
            runtime=runtime,
        )
        result = await service.create(
            authority=authority,
            command=_payment_destination_command(body),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _payment_destination_http_exception(exc) from exc
    return _payment_destination_response(result)


@router.post(
    "/payment-destinations/create-and-validate",
    response_model=PaymentDestinationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_and_validate_payment_destination(
    body: PaymentDestinationCreateRequest,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
        min_length=16,
        max_length=128,
    ),
) -> PaymentDestinationResponse:
    try:
        service = _payment_destination_service(runtime)
        authority = await _payment_destination_authority(
            current_user=current_user,
            runtime=runtime,
        )
        result = await service.create_and_validate(
            authority=authority,
            command=_payment_destination_command(body),
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _payment_destination_http_exception(exc) from exc
    return _payment_destination_response(result)


@router.get(
    "/payment-destinations",
    response_model=PaymentDestinationListResponse,
)
async def list_payment_destinations(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
) -> PaymentDestinationListResponse:
    try:
        service = _payment_destination_service(runtime)
        authority = await _payment_destination_authority(
            current_user=current_user,
            runtime=runtime,
        )
        results = await service.list_destinations(authority=authority)
    except HTTPException:
        raise
    except Exception as exc:
        raise _payment_destination_http_exception(exc) from exc
    items = tuple(_payment_destination_response(item) for item in results)
    return PaymentDestinationListResponse(items=items, count=len(items))


@router.get(
    "/payment-destinations/default",
    response_model=PaymentDestinationResponse,
)
async def get_default_payment_destination(
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
) -> PaymentDestinationResponse:
    try:
        service = _payment_destination_service(runtime)
        authority = await _payment_destination_authority(
            current_user=current_user,
            runtime=runtime,
        )
        result = await service.get_default_destination(
            authority=authority,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _payment_destination_http_exception(exc) from exc
    return _payment_destination_response(result)


@router.get(
    "/payment-destinations/{destination_ref}",
    response_model=PaymentDestinationResponse,
)
async def get_payment_destination(
    destination_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
) -> PaymentDestinationResponse:
    try:
        service = _payment_destination_service(runtime)
        authority = await _payment_destination_authority(
            current_user=current_user,
            runtime=runtime,
        )
        result = await service.get_destination(
            authority=authority,
            destination_ref=destination_ref,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _payment_destination_http_exception(exc) from exc
    return _payment_destination_response(result)


async def _transition_payment_destination(
    *,
    action: str,
    destination_ref: str,
    correlation_id: str,
    current_user: dict,
    runtime: AdminMarketplaceRuntime,
) -> PaymentDestinationResponse:
    try:
        service = _payment_destination_service(runtime)
        authority = await _payment_destination_authority(
            current_user=current_user,
            runtime=runtime,
        )
        operation = getattr(service, action)
        result = await operation(
            authority=authority,
            destination_ref=destination_ref,
            correlation_id=correlation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise _payment_destination_http_exception(exc) from exc
    return _payment_destination_response(result)


@router.post(
    "/payment-destinations/{destination_ref}/validate",
    response_model=PaymentDestinationResponse,
)
async def validate_payment_destination(
    destination_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
) -> PaymentDestinationResponse:
    return await _transition_payment_destination(
        action="validate",
        destination_ref=destination_ref,
        correlation_id=correlation_id,
        current_user=current_user,
        runtime=runtime,
    )


@router.post(
    "/payment-destinations/{destination_ref}/activate",
    response_model=PaymentDestinationResponse,
)
async def activate_payment_destination(
    destination_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
) -> PaymentDestinationResponse:
    return await _transition_payment_destination(
        action="activate",
        destination_ref=destination_ref,
        correlation_id=correlation_id,
        current_user=current_user,
        runtime=runtime,
    )


@router.post(
    "/payment-destinations/{destination_ref}/deactivate",
    response_model=PaymentDestinationResponse,
)
async def deactivate_payment_destination(
    destination_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
) -> PaymentDestinationResponse:
    return await _transition_payment_destination(
        action="deactivate",
        destination_ref=destination_ref,
        correlation_id=correlation_id,
        current_user=current_user,
        runtime=runtime,
    )


@router.post(
    "/payment-destinations/{destination_ref}/set-default",
    response_model=PaymentDestinationResponse,
)
async def set_default_payment_destination(
    destination_ref: str,
    current_user: dict = Depends(get_identity_user),
    runtime: AdminMarketplaceRuntime = Depends(
        get_admin_marketplace_runtime,
    ),
    correlation_id: str = Header(
        ...,
        alias="X-Correlation-ID",
        min_length=1,
        max_length=128,
    ),
) -> PaymentDestinationResponse:
    return await _transition_payment_destination(
        action="set_default",
        destination_ref=destination_ref,
        correlation_id=correlation_id,
        current_user=current_user,
        runtime=runtime,
    )


__all__ = [
    "AdminMarketplaceEligibilityResponse",
    "GENERIC_UNAVAILABLE",
    "MAX_ADMIN_MARKETPLACE_REQUEST_BYTES",
    "PaymentDestinationCreateRequest",
    "PaymentDestinationListResponse",
    "PaymentDestinationResponse",
    "PaymentEvidenceListResponse",
    "PaymentEvidenceReadResponse",
    "PaymentVerificationRequest",
    "PaymentVerificationResponse",
    "activate_payment_destination",
    "create_and_validate_payment_destination",
    "create_payment_destination",
    "deactivate_payment_destination",
    "get_default_payment_destination",
    "get_admin_marketplace_eligibility",
    "get_admin_marketplace_runtime",
    "get_payment_destination",
    "list_payment_destinations",
    "list_admin_marketplace_payment_evidence",
    "router",
    "set_default_payment_destination",
    "validate_payment_destination",
    "verify_admin_marketplace_payment",
]
