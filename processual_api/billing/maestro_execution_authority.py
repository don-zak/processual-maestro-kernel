from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

EXECUTION_AUTHORITY_VERSION = "maestro-execution-authority-r2b"
DISCOVERY_ONLY = True
RUNTIME_INSTRUMENTATION_ENABLED = False

LLM_CONNECTION_POLICY = "byok_only"
PLATFORM_OWNED_LLM_KEYS_ALLOWED = False
LLM_CREDENTIALS_REQUIRED_FOR_LIVE_CALLS = True
LLM_CREDENTIALS_ALLOWED_IN_MEASUREMENTS = False
LLM_RAW_PROMPTS_ALLOWED_IN_MEASUREMENTS = False
LLM_RAW_RESPONSES_ALLOWED_IN_MEASUREMENTS = False
APPROVED_FOR_QUOTA = False
APPROVED_FOR_INVOICING = False
APPROVED_FOR_CHECKOUT = False
APPROVED_FOR_SETTLEMENT = False


class MaestroExecutionAuthorityValidationError(ValueError):
    """Raised when execution-authority evidence is incomplete or unsafe."""


class MaestroExecutionAuthorityKind(StrEnum):
    LLM_ADAPTER = "llm_adapter"
    DIRECT_PROVIDER_CALL = "direct_provider_call"
    ADAPTIVE_RUNTIME_COMMAND = "adaptive_runtime_command"
    DELIVERY_DISPATCH = "delivery_dispatch"
    CONNECTOR_RUNTIME = "connector_runtime"
    AGENT_RUNTIME = "agent_runtime"
    UNKNOWN = "unknown"


class MaestroExecutionCompletionStatus(StrEnum):
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DUPLICATE = "duplicate"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class MaestroExecutionAttemptContext:
    execution_id: str
    attempt_id: str
    authority_kind: MaestroExecutionAuthorityKind
    started_at: datetime
    retry_ordinal: int = 0
    idempotency_key: str | None = None
    parent_execution_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier("execution_id", self.execution_id)
        _require_identifier("attempt_id", self.attempt_id)

        if self.parent_execution_id is not None:
            _require_identifier(
                "parent_execution_id",
                self.parent_execution_id,
            )

        if self.idempotency_key is not None:
            _require_identifier(
                "idempotency_key",
                self.idempotency_key,
            )

        _require_utc("started_at", self.started_at)

        if not isinstance(
            self.authority_kind,
            MaestroExecutionAuthorityKind,
        ):
            raise MaestroExecutionAuthorityValidationError("authority_kind must be MaestroExecutionAuthorityKind")

        if not isinstance(self.retry_ordinal, int) or isinstance(self.retry_ordinal, bool) or self.retry_ordinal < 0:
            raise MaestroExecutionAuthorityValidationError("retry_ordinal must be a non-negative int")

        if self.retry_ordinal > 0 and self.idempotency_key is None:
            raise MaestroExecutionAuthorityValidationError("retried attempts require an idempotency_key")


@dataclass(frozen=True, slots=True)
class MaestroExecutionCompletion:
    context: MaestroExecutionAttemptContext
    completed_at: datetime
    status: MaestroExecutionCompletionStatus
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.context,
            MaestroExecutionAttemptContext,
        ):
            raise MaestroExecutionAuthorityValidationError("context must be MaestroExecutionAttemptContext")

        _require_utc("completed_at", self.completed_at)

        if self.completed_at < self.context.started_at:
            raise MaestroExecutionAuthorityValidationError("completed_at must not precede started_at")

        if not isinstance(
            self.status,
            MaestroExecutionCompletionStatus,
        ):
            raise MaestroExecutionAuthorityValidationError("status must be MaestroExecutionCompletionStatus")

        if self.failure_code is not None:
            _require_identifier(
                "failure_code",
                self.failure_code,
            )

        if self.status is MaestroExecutionCompletionStatus.FAILED and self.failure_code is None:
            raise MaestroExecutionAuthorityValidationError("failed completion requires failure_code")

        if self.status is not MaestroExecutionCompletionStatus.FAILED and self.failure_code is not None:
            raise MaestroExecutionAuthorityValidationError("failure_code is only allowed for failed completion")


@runtime_checkable
class MaestroExecutionObserver(Protocol):
    """Non-commercial observation boundary for a future unified runtime."""

    def attempt_started(
        self,
        context: MaestroExecutionAttemptContext,
    ) -> None: ...

    def attempt_completed(
        self,
        completion: MaestroExecutionCompletion,
    ) -> None: ...


class NoOpMaestroExecutionObserver:
    """Default observer until a unified production authority exists."""

    def attempt_started(
        self,
        context: MaestroExecutionAttemptContext,
    ) -> None:
        del context

    def attempt_completed(
        self,
        completion: MaestroExecutionCompletion,
    ) -> None:
        del completion


def _require_identifier(name: str, value: object) -> None:
    if not isinstance(value, str):
        raise MaestroExecutionAuthorityValidationError(f"{name} must be str")

    if not value or len(value) > 128:
        raise MaestroExecutionAuthorityValidationError(f"{name} must contain between 1 and 128 characters")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")

    if any(character not in allowed for character in value):
        raise MaestroExecutionAuthorityValidationError(f"{name} contains unsupported characters")


def _require_utc(name: str, value: object) -> None:
    if not isinstance(value, datetime):
        raise MaestroExecutionAuthorityValidationError(f"{name} must be datetime")

    if value.tzinfo is None:
        raise MaestroExecutionAuthorityValidationError(f"{name} must be timezone-aware")

    if value.utcoffset() != UTC.utcoffset(value):
        raise MaestroExecutionAuthorityValidationError(f"{name} must use UTC")
