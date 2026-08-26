from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationContractViolationError,
    PrivateEvaluationRequest,
    PrivateEvaluationUnavailableError,
    SanitizedPrivateDecision,
)
from processual_api.integrations.private_evaluation_runtime import (
    bind_private_evaluation_provider,
    clear_private_evaluation_provider,
    private_evaluation_provider_from_request,
)


class _Provider:
    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        del request
        return SanitizedPrivateDecision(
            existence_rank="B",
            dominant_constraint="constraint.none",
            next_gate="gate.review",
            confidence_band="medium",
            explanation_code="private-evaluation-ok",
            policy_version="policy.v1",
        )


def _request(app: FastAPI) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "app": app})


def test_runtime_binding_defaults_to_unavailable() -> None:
    app = FastAPI()
    with pytest.raises(PrivateEvaluationUnavailableError, match="^private_evaluation_unavailable$") as exc_info:
        private_evaluation_provider_from_request(_request(app))

    assert exc_info.value.__cause__ is None


def test_runtime_binding_returns_only_explicitly_injected_provider() -> None:
    app = FastAPI()
    provider = _Provider()
    bind_private_evaluation_provider(app, provider)

    assert private_evaluation_provider_from_request(_request(app)) is provider


def test_runtime_binding_clear_restores_default_deny() -> None:
    app = FastAPI()
    bind_private_evaluation_provider(app, _Provider())
    clear_private_evaluation_provider(app)

    with pytest.raises(PrivateEvaluationUnavailableError, match="^private_evaluation_unavailable$"):
        private_evaluation_provider_from_request(_request(app))


def test_runtime_binding_rejects_non_provider_without_echoing_values() -> None:
    app = FastAPI()
    secret_value = "proprietary-provider-state-must-not-leak"

    with pytest.raises(PrivateEvaluationContractViolationError, match="^private_evaluation_contract_violation$") as exc_info:
        bind_private_evaluation_provider(app, secret_value)  # type: ignore[arg-type]

    assert secret_value not in str(exc_info.value)


def test_public_runtime_binding_source_cannot_discover_private_modules() -> None:
    source = Path("processual_api/integrations/private_evaluation_runtime.py").read_text("utf-8")
    forbidden = (
        "processual_api.private_integrations",
        "cgtlib.private",
        "import_module",
        "find_spec",
        "private_integrations",
    )
    assert all(token not in source for token in forbidden)
