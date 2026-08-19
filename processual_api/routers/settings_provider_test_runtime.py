from __future__ import annotations

import os
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.routing import APIRoute

from processual_api.auth.security import get_current_user
from processual_api.cgt_governor.adapters.provider_metadata import provider_ids
from processual_api.routers import settings as settings_module
from processual_api.schemas.settings import LLMProviderConfig, TestConnectionResult

settings_router = settings_module.router
_runtime_router = APIRouter(prefix="/settings", tags=["settings"])

_SECRET_OPTIONAL_PROVIDERS = {"opencode", "generic_openai_compatible"}


def _stored_provider_secret(user_id: str) -> str:
    raw = settings_module._load_raw(user_id)
    encrypted = raw.get("llm_provider", {}).get("encrypted_key")
    if not encrypted:
        return ""
    return settings_module._decrypt_api_key(encrypted) or ""


async def run_provider_connection_test(
    config: LLMProviderConfig,
    current_user: dict,
) -> TestConnectionResult:
    user_id = current_user.get("sub", "default")
    provider = str(config.provider or "").strip().lower()
    if provider not in provider_ids():
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    api_key = str(config.api_key or "").strip() or _stored_provider_secret(user_id)
    if not api_key and provider not in _SECRET_OPTIONAL_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is required",
        )

    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if provider == "openai":
                response = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elif provider == "anthropic":
                response = await client.get(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
            elif provider == "gemini":
                response = await client.get(
                    f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
                )
            elif provider == "deepseek":
                response = await client.get(
                    "https://api.deepseek.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            elif provider == "opencode":
                base_url = os.environ.get(
                    "OPENCODE_API_URL",
                    "http://localhost:11434/v1",
                ).rstrip("/")
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                )
            elif provider == "openrouter":
                base_url = os.environ.get(
                    "OPENROUTER_API_URL",
                    "https://openrouter.ai/api/v1",
                ).rstrip("/")
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            else:
                base_url = os.environ.get("GENERIC_OPENAI_API_URL", "").rstrip("/")
                if not base_url:
                    return TestConnectionResult(
                        success=False,
                        error="GENERIC_OPENAI_API_URL is required",
                    )
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                )

        latency = (time.time() - start) * 1000
        if response.status_code == 200:
            return TestConnectionResult(success=True, latency_ms=round(latency, 1))
        return TestConnectionResult(
            success=False,
            error=f"HTTP {response.status_code}: Provider returned non-200",
        )
    except httpx.TimeoutException:
        return TestConnectionResult(
            success=False,
            error="Connection timed out after 10s",
        )
    except Exception as exc:
        return TestConnectionResult(success=False, error=str(exc)[:200])


@_runtime_router.post(
    "/provider-connection/test",
    response_model=TestConnectionResult,
)
async def test_provider_connection_runtime(
    body: settings_module.ClientProviderConnectionSetupPayload,
    current_user: dict = Depends(get_current_user),
) -> TestConnectionResult:
    provider = settings_module._normalize_client_provider(body.provider)
    return await run_provider_connection_test(
        LLMProviderConfig(
            provider=provider,
            api_key=str(body.provider_secret or "").strip(),
            model=str(body.model or "").strip(),
        ),
        current_user,
    )


@_runtime_router.post(
    "/llm-provider/test",
    response_model=TestConnectionResult,
    deprecated=True,
)
async def test_legacy_llm_provider_runtime(
    body: LLMProviderConfig,
    response: Response,
    current_user: dict = Depends(get_current_user),
) -> TestConnectionResult:
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = (
        '</settings/provider-connection/test>; rel="successor-version"'
    )
    return await run_provider_connection_test(body, current_user)


def install_provider_test_routes(target_router: APIRouter) -> None:
    replaced_paths = {
        "/settings/provider-connection/test",
        "/settings/llm-provider/test",
    }
    target_router.routes[:] = [
        route
        for route in target_router.routes
        if not (
            isinstance(route, APIRoute)
            and route.path in replaced_paths
            and "POST" in route.methods
        )
    ]
    target_router.routes.extend(_runtime_router.routes)


install_provider_test_routes(settings_router)