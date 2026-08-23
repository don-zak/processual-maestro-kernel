"""Generic external-agent adapter for governed execution qualification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

from .execution_enforcement import GovernedAgentExecutionRequest


class ExternalAgentExecutionError(RuntimeError):
    """Raised when an external governed execution cannot complete safely."""


class ExternalAgentTransport(Protocol):
    def invoke(self, *, endpoint: str, payload: dict[str, object]) -> str: ...


@dataclass(frozen=True, slots=True)
class ExternalAgentTarget:
    agent_id: str
    endpoint: str

    def validate(self) -> None:
        if not self.agent_id or self.agent_id != self.agent_id.strip():
            raise ExternalAgentExecutionError("invalid_external_agent_id")
        parsed = urlparse(self.endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ExternalAgentExecutionError("invalid_external_agent_endpoint")
        if parsed.username or parsed.password or parsed.fragment:
            raise ExternalAgentExecutionError("invalid_external_agent_endpoint")


class GenericExternalAgentAdapter:
    """ActionExecutor-compatible adapter that keeps transport/auth outside governance."""

    def __init__(self, *, target: ExternalAgentTarget, transport: ExternalAgentTransport) -> None:
        target.validate()
        self._target = target
        self._transport = transport

    def execute(self, request: GovernedAgentExecutionRequest, *, restricted: bool) -> str:
        return self._invoke(request, operation="execute", restricted=restricted)

    def repair(self, request: GovernedAgentExecutionRequest) -> str:
        return self._invoke(request, operation="repair", restricted=True)

    def retry(self, request: GovernedAgentExecutionRequest) -> str:
        return self._invoke(request, operation="retry", restricted=True)

    def _invoke(
        self,
        request: GovernedAgentExecutionRequest,
        *,
        operation: str,
        restricted: bool,
    ) -> str:
        if request.agent_id != self._target.agent_id:
            raise ExternalAgentExecutionError("external_agent_binding_mismatch")
        payload: dict[str, object] = {
            "agent_id": request.agent_id,
            "evaluation_id": request.evaluation_id,
            "task_ref": request.task_ref,
            "audit_ref": request.audit_ref,
            "operation": operation,
            "restricted": restricted,
        }
        try:
            execution_ref = self._transport.invoke(endpoint=self._target.endpoint, payload=payload)
        except Exception as exc:
            raise ExternalAgentExecutionError("external_agent_transport_failed") from exc
        if not isinstance(execution_ref, str) or not execution_ref.strip():
            raise ExternalAgentExecutionError("invalid_external_execution_ref")
        return execution_ref.strip()
