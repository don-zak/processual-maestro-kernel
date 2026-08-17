"""Billing routes backed by authoritative commercial services."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response

from processual_api.admin_marketplace.lemon_squeezy_secure_webhook_router import (
    install_secure_lemon_squeezy_webhook_route,
)
from processual_api.admin_marketplace.subscription_access import (
    resolve_subscription_access,
)
from processual_api.auth.security import get_current_user
from processual_api.auth.session_router import get_identity_user
from processual_api.billing.customer_billing_authority import (
    BillingAuthorityError,
    load_billing_authority_snapshot,
)
from processual_api.billing.customer_billing_statements import (
    BillingStatementIntegrityError,
    build_billing_statement,
    list_statements,
    load_statement,
    persist_statement,
    read_client_settings,
    read_usage_records,
    render_statement_pdf,
)
from processual_api.billing.direct_checkout_router import (
    router as direct_checkout_router,
)
from processual_api.billing.offer_pricebook import public_offer_pricebook
from processual_api.billing.plan_capability_router import (
    router as plan_capability_router,
)
from processual_api.billing.pricing_catalog import public_subscription_catalog
from processual_api.billing.public_plan_journey import (
    public_plan_journey_catalog,
)
from processual_api.billing.subscription_preparation import (
    build_subscription_preparation,
)
from processual_api.billing.subscription_preparation_repository import (
    SqlAlchemySubscriptionPreparationRepository,
)
from processual_api.billing.unit_cost_assumptions import (
    get_unit_cost_assumptions as build_unit_cost_assumptions,
)
from processual_api.db.session import get_session_factory

router = APIRouter(prefix="/billing", tags=["billing"])
router.routes.extend(direct_checkout_router.routes)
router.routes.extend(plan_capability_router.routes)
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_VARIANTS = {
    "starter": os.environ.get("LS_VARIANT_STARTER", ""),
    "starter_yearly": os.environ.get("LS_VARIANT_STARTER_YEARLY", ""),
    "professional": os.environ.get("LS_VARIANT_PROFESSIONAL", ""),
    "professional_yearly": os.environ.get(
        "LS_VARIANT_PROFESSIONAL_YEARLY",
        "",
    ),
    "enterprise": os.environ.get("LS_VARIANT_ENTERPRISE", ""),
    "enterprise_yearly": os.environ.get("LS_VARIANT_ENTERPRISE_YEARLY", ""),
}


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise HTTPException(
            status_code=503,
            detail="Billing service is temporarily unavailable.",
        )
    return value


def _identity_customer_ref(current_user: dict) -> str:
    candidate = (
        current_user.get("organization_id")
        or current_user.get("user_id")
        or current_user.get("sub")
    )
    try:
        return str(uuid.UUID(str(candidate)))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=403,
            detail="Billing access denied.",
        ) from exc


def _billing_user_id(current_user: dict) -> str:
    return str(
        current_user.get("user_id")
        or current_user.get("sub")
        or ""
    ).strip()


def _require_billing_admin(current_user: dict) -> None:
    role = str(
        current_user.get("role")
        or current_user.get("admin_role")
        or ""
    ).strip()
    raw_scopes = (
        current_user.get("scopes")
        or current_user.get("permissions")
        or []
    )
    if isinstance(raw_scopes, str):
        raw_scopes = [raw_scopes]
    scopes = {
        str(scope).strip()
        for scope in raw_scopes
        if str(scope).strip()
    }

    if role in {
        "admin",
        "administrator",
        "owner_admin",
        "billing_admin",
    }:
        return
    if scopes.intersection(
        {
            "admin:*",
            "admin:billing:read",
            "admin:billing:write",
        }
    ):
        return
    raise HTTPException(
        status_code=403,
        detail="Billing statement supervisor access denied.",
    )


def _statement_summary(
    statement: dict[str, Any],
    *,
    admin: bool = False,
) -> dict[str, Any]:
    prefix = "/billing/admin/statements" if admin else "/billing/statements"
    return {
        "statement_ref": statement["statement_ref"],
        "statement_sha256": statement["statement_sha256"],
        "issued_at": statement["issued_at"],
        "client_id": statement["client_id"],
        "period": statement["billing_period"]["period"],
        "plan_id": statement["plan"]["plan_id"],
        "consumed_units": statement["balance"]["consumed_units"],
        "remaining_units": statement["balance"]["remaining_units"],
        "top_up_units": statement["balance"]["top_up_units"],
        "additional_package_count": len(
            statement.get("additional_packages")
            or []
        ),
        "reconciled": bool(
            statement["reconciliation"]["reconciled"]
        ),
        "top_ups_reconciled": bool(
            statement["reconciliation"]["top_ups_reconciled"]
        ),
        "pdf_url": (
            f"{prefix}/{statement['statement_ref']}/pdf"
        ),
    }


def _existing_period_statement(
    *,
    client_id: str,
    period: str,
) -> dict[str, Any] | None:
    matches = [
        statement
        for statement in list_statements(
            _DATA_DIR,
            client_id=client_id,
        )
        if str(
            statement.get("billing_period", {}).get("period")
            or ""
        )
        == period
    ]
    if len(matches) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                "Multiple immutable billing statements exist "
                "for this client and period."
            ),
        )
    return matches[0] if matches else None


async def _issue_statement(
    *,
    client_id: str,
    user_id: str,
    period: str,
) -> dict[str, Any]:
    existing = _existing_period_statement(
        client_id=client_id,
        period=period,
    )
    if existing is not None:
        return existing

    try:
        quota_cycle, granted_top_ups = (
            await load_billing_authority_snapshot(
                client_id=client_id,
                period=period,
            )
        )
        statement = build_billing_statement(
            client_id=client_id,
            user_id=user_id,
            period=period,
            usage_records=read_usage_records(_DATA_DIR),
            raw_settings=read_client_settings(
                _DATA_DIR,
                user_id,
            ),
            quota_cycle=quota_cycle,
            granted_top_ups=granted_top_ups,
        )
        return persist_statement(_DATA_DIR, statement)
    except (
        BillingAuthorityError,
        BillingStatementIntegrityError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Billing statement authority is unavailable.",
        ) from exc


def _load_verified_statement(
    statement_ref: str,
) -> dict[str, Any]:
    try:
        return load_statement(_DATA_DIR, statement_ref)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Billing statement not found.",
        ) from exc
    except BillingStatementIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Billing statement integrity verification failed."
            ),
        ) from exc


def _pdf_response(statement: dict[str, Any]) -> Response:
    try:
        content = render_statement_pdf(statement)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Billing statement PDF rendering is unavailable.",
        ) from exc
    except BillingStatementIntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Billing statement integrity verification failed."
            ),
        ) from exc

    statement_ref = str(statement["statement_ref"])
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{statement_ref}.pdf"'
            ),
            "X-Maestro-Statement-SHA256": (
                statement["statement_sha256"]
            ),
        },
    )


@router.post("/checkout", response_model=dict)
async def create_checkout(
    body: dict,
    current_user: dict = Depends(get_current_user),
) -> dict[str, object]:
    api_key = _required_environment("LEMONSQUEEZY_API_KEY")
    store_id = _required_environment("LEMONSQUEEZY_STORE_ID")
    success_url = _required_environment(
        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL"
    )
    cancel_url = _required_environment(
        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL"
    )

    variant_id = str(body.get("variant_id") or "").strip()
    if not variant_id:
        plan = str(
            body.get("plan") or "professional"
        ).strip().lower()
        billing_period = str(
            body.get("billing") or "monthly"
        ).strip().lower()
        variant_key = (
            f"{plan}_yearly"
            if billing_period == "yearly"
            else plan
        )
        variant_id = _VARIANTS.get(variant_key, "").strip()

    if not variant_id.isdigit() or not store_id.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Invalid checkout request.",
        )

    customer_ref = _identity_customer_ref(current_user)
    email = str(body.get("email") or "").strip()

    try:
        import httpx

        attributes: dict[str, Any] = {
            "store_id": int(store_id),
            "variant_id": int(variant_id),
            "success_url": success_url,
            "cancel_url": cancel_url,
            "custom_data": {
                "customer_ref": customer_ref,
            },
        }
        if email:
            attributes["customer_email"] = email
        payload = {
            "data": {
                "type": "checkouts",
                "attributes": attributes,
            }
        }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.lemonsqueezy.com/v1/checkouts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/vnd.api+json",
                },
            )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Billing service is temporarily unavailable.",
        ) from exc

    if response.status_code not in {200, 201}:
        raise HTTPException(
            status_code=502,
            detail="Payment provider request failed.",
        )
    data = response.json().get("data", {})
    return {
        "url": data.get("attributes", {}).get("url", ""),
        "checkout_id": data.get("id", ""),
    }


@router.get("/portal", response_model=dict)
async def customer_portal(
    current_user: dict = Depends(get_identity_user),
) -> dict[str, object]:
    customer_ref = _identity_customer_ref(current_user)
    try:
        snapshot = await resolve_subscription_access(customer_ref)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Billing service is temporarily unavailable.",
        ) from exc
    if snapshot is None:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found.",
        )
    raise HTTPException(
        status_code=409,
        detail=(
            "Customer portal is unavailable until "
            "provider binding is verified."
        ),
    )


@router.get("/subscription-preparation", response_model=dict)
async def get_subscription_preparation(
    current_user: dict = Depends(get_identity_user),
) -> dict[str, object]:
    try:
        user_id = uuid.UUID(str(current_user["user_id"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid identity session.",
        ) from exc

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            repository = (
                SqlAlchemySubscriptionPreparationRepository(session)
            )
            return await build_subscription_preparation(
                repository=repository,
                user_id=user_id,
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Subscription preparation is unavailable.",
        ) from exc


@router.get("/subscription", response_model=dict)
async def get_billing_subscription(
    current_user: dict = Depends(get_current_user),
) -> dict[str, object]:
    customer_ref = _identity_customer_ref(current_user)
    try:
        snapshot = await resolve_subscription_access(customer_ref)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Billing service is temporarily unavailable.",
        ) from exc

    if snapshot is None:
        return {
            "plan": None,
            "status": "inactive",
            "billing_provider": "lemonsqueezy",
            "has_subscription": False,
        }
    return {
        "subscription_id": str(snapshot.subscription_id),
        "plan": snapshot.entitlement_profile_ref,
        "status": snapshot.access_stage,
        "renews_at": snapshot.grace_until,
        "billing_provider": "lemonsqueezy",
        "has_subscription": True,
    }


@router.get("/statements", response_model=dict)
async def list_customer_billing_statements(
    current_user: dict = Depends(get_identity_user),
) -> dict[str, Any]:
    client_id = _identity_customer_ref(current_user)
    items = [
        _statement_summary(item)
        for item in list_statements(
            _DATA_DIR,
            client_id=client_id,
        )
    ]
    return {
        "status": "ready",
        "client_id": client_id,
        "statement_count": len(items),
        "statements": items,
    }


@router.post(
    "/statements/{period}",
    response_model=dict,
    status_code=201,
)
async def issue_customer_billing_statement(
    period: str,
    current_user: dict = Depends(get_identity_user),
) -> dict[str, Any]:
    client_id = _identity_customer_ref(current_user)
    user_id = _billing_user_id(current_user) or client_id
    statement = await _issue_statement(
        client_id=client_id,
        user_id=user_id,
        period=period,
    )
    return {
        "status": "issued",
        "statement": statement,
    }


@router.get("/statements/{statement_ref}", response_model=dict)
async def get_customer_billing_statement(
    statement_ref: str,
    current_user: dict = Depends(get_identity_user),
) -> dict[str, Any]:
    client_id = _identity_customer_ref(current_user)
    statement = _load_verified_statement(statement_ref)
    if str(statement.get("client_id") or "") != client_id:
        raise HTTPException(
            status_code=404,
            detail="Billing statement not found.",
        )
    return {
        "status": "verified",
        "statement": statement,
    }


@router.get("/statements/{statement_ref}/pdf")
async def download_customer_billing_statement_pdf(
    statement_ref: str,
    current_user: dict = Depends(get_identity_user),
) -> Response:
    client_id = _identity_customer_ref(current_user)
    statement = _load_verified_statement(statement_ref)
    if str(statement.get("client_id") or "") != client_id:
        raise HTTPException(
            status_code=404,
            detail="Billing statement not found.",
        )
    return _pdf_response(statement)


@router.get("/admin/statements", response_model=dict)
async def list_admin_billing_statements(
    client_id: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _require_billing_admin(current_user)
    items = [
        _statement_summary(item, admin=True)
        for item in list_statements(
            _DATA_DIR,
            client_id=client_id,
        )
    ]
    return {
        "status": "ready",
        "statement_count": len(items),
        "statements": items,
    }


@router.post(
    "/admin/statements/{client_id}/{period}",
    response_model=dict,
    status_code=201,
)
async def issue_admin_billing_statement(
    client_id: str,
    period: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _require_billing_admin(current_user)
    try:
        normalized_client_id = str(uuid.UUID(client_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid billing client identifier.",
        ) from exc

    statement = await _issue_statement(
        client_id=normalized_client_id,
        user_id=normalized_client_id,
        period=period,
    )
    return {
        "status": "issued",
        "statement": statement,
    }


@router.get("/admin/statements/{statement_ref}", response_model=dict)
async def get_admin_billing_statement(
    statement_ref: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    _require_billing_admin(current_user)
    return {
        "status": "verified",
        "statement": _load_verified_statement(statement_ref),
    }


@router.get("/admin/statements/{statement_ref}/pdf")
async def download_admin_billing_statement_pdf(
    statement_ref: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    _require_billing_admin(current_user)
    statement = _load_verified_statement(statement_ref)
    return _pdf_response(statement)


@router.get("/public-plan-journey")
async def get_public_plan_journey() -> dict[str, object]:
    return public_plan_journey_catalog()


@router.get("/pricing-catalog")
async def get_pricing_catalog() -> dict[str, object]:
    return public_subscription_catalog()


@router.get("/offer-pricebook")
async def get_offer_pricebook() -> dict[str, object]:
    return public_offer_pricebook()


@router.get("/unit-cost-assumptions")
async def get_unit_cost_assumptions() -> dict[str, object]:
    """Return the public-safe draft unit cost assumptions model."""
    return build_unit_cost_assumptions()


install_secure_lemon_squeezy_webhook_route(router)
