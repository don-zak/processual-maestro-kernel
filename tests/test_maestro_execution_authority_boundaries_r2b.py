import ast
from pathlib import Path

AUTHORITY_PATH = Path("processual_api/billing/maestro_execution_authority.py")

FORBIDDEN_IMPORT_FRAGMENTS = {
    "usage_pricing",
    "usage_log",
    "quota",
    "subscription",
    "checkout",
    "invoice",
    "payment",
    "middleware",
    "routers",
    "cgt_governor",
    "integrations",
    "adaptive.runtime_adapter",
    "agent_runtime",
}


def test_execution_authority_has_no_runtime_or_commercial_imports():
    tree = ast.parse(
        AUTHORITY_PATH.read_text(encoding="utf-8-sig"),
        filename=str(AUTHORITY_PATH),
    )

    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    violations = [
        imported for imported in imports if any(fragment in imported for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    ]

    assert violations == []


def test_execution_authority_does_not_construct_shadow_measurements():
    source = AUTHORITY_PATH.read_text(encoding="utf-8-sig")

    assert "MaestroShadowMeasurement(" not in source
    assert "MaestroShadowMeasurementStore(" not in source


FORBIDDEN_EXECUTION_CONTEXT_FIELDS = frozenset(
    {
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
    }
)


def test_execution_context_has_no_raw_secret_or_payload_fields() -> None:
    from dataclasses import fields

    from processual_api.billing.maestro_execution_authority import (
        MaestroExecutionAttemptContext,
    )

    field_names = {field.name.lower() for field in fields(MaestroExecutionAttemptContext)}

    assert field_names.isdisjoint(FORBIDDEN_EXECUTION_CONTEXT_FIELDS)


def test_execution_authority_does_not_resolve_provider_secrets() -> None:
    import ast
    from pathlib import Path

    module_path = Path(__file__).parents[1] / "processual_api" / "billing" / "maestro_execution_authority.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    forbidden_import_fragments = {
        "processual_api.settings",
        "processual_api.adapters.llm",
        "processual_api.cgt_governor.reports.llm_reporter",
        "openai",
        "anthropic",
        "google.generativeai",
        "httpx",
        "requests",
    }

    assert not any(
        imported == forbidden or imported.startswith(f"{forbidden}.")
        for imported in imported_modules
        for forbidden in forbidden_import_fragments
    )
