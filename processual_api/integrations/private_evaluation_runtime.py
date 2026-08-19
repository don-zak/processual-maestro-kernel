from __future__ import annotations

from fastapi import FastAPI, Request

from .private_evaluation_boundary import (
    PrivateEvaluationContractViolationError,
    PrivateEvaluationProvider,
    PrivateEvaluationUnavailableError,
)

_PROVIDER_STATE_KEY = "private_evaluation_provider"


def bind_private_evaluation_provider(app: FastAPI, provider: PrivateEvaluationProvider) -> None:
    """Bind a private provider supplied by a controlled deployment composition root."""
    if not isinstance(provider, PrivateEvaluationProvider):
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    setattr(app.state, _PROVIDER_STATE_KEY, provider)


def clear_private_evaluation_provider(app: FastAPI) -> None:
    """Remove any bound private provider and restore default-deny behavior."""
    if hasattr(app.state, _PROVIDER_STATE_KEY):
        delattr(app.state, _PROVIDER_STATE_KEY)


def private_evaluation_provider_from_request(request: Request) -> PrivateEvaluationProvider:
    """Resolve only an explicitly injected provider; never discover private source."""
    provider = getattr(request.app.state, _PROVIDER_STATE_KEY, None)
    if provider is None:
        raise PrivateEvaluationUnavailableError("private_evaluation_unavailable")
    if not isinstance(provider, PrivateEvaluationProvider):
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    return provider
