from __future__ import annotations

import re
from dataclasses import dataclass, fields
from typing import Protocol, runtime_checkable

_BOUNDARY_CONTRACT_VERSION = "private-evaluation-boundary/v1"
_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.:@/\-]+$")
_MAX_TOKEN_LENGTH = 96
_ALLOWED_RESULT_FIELDS = (
    "existence_rank",
    "dominant_constraint",
    "next_gate",
    "confidence_band",
    "explanation_code",
    "policy_version",
)


class PrivateEvaluationBoundaryError(RuntimeError):
    """Base error for the public/private evaluation trust boundary."""


class PrivateEvaluationUnavailableError(PrivateEvaluationBoundaryError):
    """Raised when the private provider cannot safely complete evaluation."""


class PrivateEvaluationContractViolationError(PrivateEvaluationBoundaryError):
    """Raised when a provider returns data outside the sanitized contract."""


@dataclass(frozen=True, slots=True)
class PrivateEvaluationRequest:
    """Reference-only request crossing from public governance into private execution.

    The public side carries opaque references only. Resolution of proprietary
    mathematical inputs and all private computation remains an implementation
    concern of the private execution environment.
    """

    formation_ref: str
    evidence_ref: str
    context_ref: str
    evaluated_at: str


@dataclass(frozen=True, slots=True)
class SanitizedPrivateDecision:
    """Strictly bounded decision surface permitted to return to public governance."""

    existence_rank: str
    dominant_constraint: str
    next_gate: str
    confidence_band: str
    explanation_code: str
    policy_version: str


@runtime_checkable
class PrivateEvaluationProvider(Protocol):
    """Opaque provider implemented and composed only by the private runtime."""

    def evaluate(self, request: PrivateEvaluationRequest) -> SanitizedPrivateDecision:
        """Return only a sanitized decision for the supplied opaque references."""


def boundary_contract_version() -> str:
    return _BOUNDARY_CONTRACT_VERSION


def _validate_token(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    candidate = value.strip()
    if not candidate or candidate != value:
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    if len(candidate) > _MAX_TOKEN_LENGTH or _SAFE_TOKEN.fullmatch(candidate) is None:
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    return candidate


def validate_private_evaluation_request(request: PrivateEvaluationRequest) -> PrivateEvaluationRequest:
    """Validate that the public-to-private envelope contains bounded opaque references only."""

    if not isinstance(request, PrivateEvaluationRequest):
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    return PrivateEvaluationRequest(
        formation_ref=_validate_token("formation_ref", request.formation_ref),
        evidence_ref=_validate_token("evidence_ref", request.evidence_ref),
        context_ref=_validate_token("context_ref", request.context_ref),
        evaluated_at=_validate_token("evaluated_at", request.evaluated_at),
    )


def validate_sanitized_private_decision(decision: SanitizedPrivateDecision) -> SanitizedPrivateDecision:
    """Fail closed unless the private result is exactly the approved bounded shape."""

    if not isinstance(decision, SanitizedPrivateDecision):
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    if tuple(field.name for field in fields(decision)) != _ALLOWED_RESULT_FIELDS:
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    return SanitizedPrivateDecision(
        existence_rank=_validate_token("existence_rank", decision.existence_rank),
        dominant_constraint=_validate_token("dominant_constraint", decision.dominant_constraint),
        next_gate=_validate_token("next_gate", decision.next_gate),
        confidence_band=_validate_token("confidence_band", decision.confidence_band),
        explanation_code=_validate_token("explanation_code", decision.explanation_code),
        policy_version=_validate_token("policy_version", decision.policy_version),
    )


def evaluate_through_private_boundary(
    provider: PrivateEvaluationProvider,
    request: PrivateEvaluationRequest,
) -> SanitizedPrivateDecision:
    """Invoke an injected private provider without exposing its implementation or failures.

    Provider exceptions are intentionally discarded before the public boundary
    raises a generic failure. This prevents private exception messages, reprs,
    stack details, or embedded values from becoming part of the public error.
    """

    safe_request = validate_private_evaluation_request(request)
    provider_failed = False
    decision: SanitizedPrivateDecision | None = None
    try:
        decision = provider.evaluate(safe_request)
    except Exception:
        provider_failed = True

    if provider_failed:
        raise PrivateEvaluationUnavailableError("private_evaluation_unavailable")
    if decision is None:
        raise PrivateEvaluationContractViolationError("private_evaluation_contract_violation")
    return validate_sanitized_private_decision(decision)
