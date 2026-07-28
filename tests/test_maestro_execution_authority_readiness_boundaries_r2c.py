import ast
from dataclasses import fields
from pathlib import Path

READINESS_PATH = Path("processual_api/billing/maestro_execution_authority_readiness.py")

FORBIDDEN_IMPORT_FRAGMENTS = {
    "adapters.llm",
    "llm_reporter",
    "openai",
    "anthropic",
    "google.genai",
    "google.generativeai",
    "httpx",
    "requests",
    "runtime_adapter",
    "agent_runtime",
    "connector",
    "middleware",
    "routers",
    "shadow_store",
    "shadow_measurement",
    "usage_pricing",
    "usage_log",
    "quota",
    "subscription",
    "checkout",
    "invoice",
    "payment",
    "settlement",
    "sqlalchemy",
    "redis",
}

FORBIDDEN_FIELD_NAMES = {
    "api_key",
    "secret",
    "secret_value",
    "token",
    "access_token",
    "authorization",
    "authorization_header",
    "bearer",
    "bearer_token",
    "password",
    "cookie",
    "prompt",
    "raw_prompt",
    "response",
    "response_body",
    "raw_request",
    "raw_response",
    "provider_payload",
}


def _parse_readiness_module() -> ast.Module:
    return ast.parse(
        READINESS_PATH.read_text(encoding="utf-8"),
        filename=str(READINESS_PATH),
    )


def test_readiness_has_no_runtime_provider_or_commercial_imports() -> None:
    tree = _parse_readiness_module()
    imported_modules: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_modules.append(node.module or "")

    violations = [
        imported
        for imported in imported_modules
        if any(fragment in imported for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    ]

    assert violations == []


def test_readiness_module_does_not_construct_runtime_objects() -> None:
    tree = _parse_readiness_module()

    forbidden_call_names = {
        "MaestroShadowMeasurement",
        "MaestroShadowMeasurementStore",
        "OpenAI",
        "Anthropic",
        "Client",
        "AsyncClient",
        "Redis",
        "create_engine",
        "create_async_engine",
    }

    called_names = {
        node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert called_names.isdisjoint(forbidden_call_names)


def test_readiness_contract_excludes_secret_and_payload_fields() -> None:
    from processual_api.billing.maestro_execution_authority_readiness import (
        MaestroExecutionAuthorityReadiness,
    )

    field_names = {field.name.lower() for field in fields(MaestroExecutionAuthorityReadiness)}

    assert field_names.isdisjoint(FORBIDDEN_FIELD_NAMES)


def test_readiness_module_exposes_no_network_or_persistence_calls() -> None:
    tree = _parse_readiness_module()

    forbidden_attributes = {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "request",
        "execute",
        "commit",
        "flush",
        "add",
        "append",
        "set",
        "save",
        "persist",
        "emit",
    }

    attribute_calls = {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert attribute_calls.isdisjoint(forbidden_attributes)
