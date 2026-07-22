from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..settings import settings
from .security import (
    _pbkdf2_hash_api_key,
    create_access_token,
    generate_api_key,
    get_current_user,
    hash_api_key,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = "admin"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class APIKeyResponse(BaseModel):
    api_key: str
    hashed_key: str


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(body: LoginRequest):
    admin_email = settings.maestro_admin_email.strip()
    admin_password = settings.maestro_admin_password

    if admin_email and admin_password:
        expected_user = admin_email
        expected_pass = admin_password
    elif settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin credentials are not configured",
        )
    else:
        expected_user = "admin"  # nosec
        expected_pass = "admin"  # nosec

    if body.username != expected_user or body.password != expected_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    login_role = body.role.strip().lower()

    if login_role == "admin":
        token = create_access_token(
            subject=body.username,
            role="admin",
            client_id="admin",
            session_type="ui_admin",
            scopes=["*"],
        )
    elif login_role in {"user", "client"} and not settings.is_production:
        token = create_access_token(
            subject=body.username,
            role="client",
            client_id=body.username,
            session_type="ui_client",
            scopes=["evaluation"],
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid login role",
        )

    return TokenResponse(access_token=token)


@router.post("/api-key", response_model=APIKeyResponse)
async def create_api_key(current_user: dict = Depends(get_current_user)):
    raw_key = generate_api_key()
    try:
        hashed = hash_api_key(raw_key)
    except RuntimeError as exc:
        if "bcrypt" not in str(exc).lower():
            raise
        hashed = _pbkdf2_hash_api_key(raw_key)
    return APIKeyResponse(api_key=raw_key, hashed_key=hashed)


@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user
