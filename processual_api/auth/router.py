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


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class APIKeyResponse(BaseModel):
    api_key: str
    hashed_key: str


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(body: LoginRequest):
    if settings.is_production:
        expected_user = settings.jwt_secret[:8]
        expected_pass = settings.jwt_secret[-8:]
    else:
        expected_user = "admin"  # nosec
        expected_pass = "admin"  # nosec

    if body.username != expected_user or body.password != expected_pass:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(
        subject=body.username,
        role="admin",
        client_id="admin",
        session_type="ui_admin",
        scopes=["*"],
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
