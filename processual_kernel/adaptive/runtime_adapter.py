from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..adaptive_types import RuntimeCommand, RuntimeCommandResult
from ..types import MaestroAction


class AdaptiveRuntimeAdapter:
    """Thin, safe adapter between adaptive recommendations and a host runtime.

    The adapter never decides policy by itself. It only turns already-authorized adaptive recommendations into
    runtime commands. This keeps the paper's boundary intact: the kernel decides, adaptive tools review, and the
    host runtime executes.
    """

    READ_ONLY_ACTIONS = {MaestroAction.OBSERVE}
    STATE_ACTIONS = {
        MaestroAction.PAUSE,
        MaestroAction.REROUTE,
        MaestroAction.ESCALATE,
        MaestroAction.FINALIZE,
    }

    def build_command(
        self,
        workflow_id: str,
        action: MaestroAction,
        subject: str | None = None,
        reason: str = "adaptive runtime command",
        payload: dict[str, Any] | None = None,
        *,
        dry_run: bool = True,
        authorized: bool = False,
        requires_human_approval: bool = False,
        request_id: str | None = None,
    ) -> RuntimeCommand:
        return RuntimeCommand(
            workflow_id=workflow_id,
            action=action,
            subject=subject or workflow_id,
            reason=reason,
            payload=payload or {},
            authorized=authorized,
            requires_human_approval=requires_human_approval,
            request_id=request_id,
            dry_run=dry_run,
        )

    def with_authorization(
        self,
        command: RuntimeCommand,
        *,
        authorized: bool,
        requires_human_approval: bool = False,
        request_id: str | None = None,
    ) -> RuntimeCommand:
        return replace(
            command,
            authorized=authorized,
            requires_human_approval=requires_human_approval,
            request_id=request_id,
        )

    def execute(self, kernel: Any, command: RuntimeCommand) -> RuntimeCommandResult:
        if command.requires_human_approval:
            return RuntimeCommandResult(
                workflow_id=command.workflow_id,
                action=command.action,
                executed=False,
                dry_run=command.dry_run,
                authorized=command.authorized,
                requires_human_approval=True,
                request_id=command.request_id,
                reason="blocked pending human approval",
                event_payload=command.payload,
            )
        if not command.authorized:
            return RuntimeCommandResult(
                workflow_id=command.workflow_id,
                action=command.action,
                executed=False,
                dry_run=command.dry_run,
                authorized=False,
                requires_human_approval=False,
                request_id=command.request_id,
                reason="blocked because command is not authorized",
                event_payload=command.payload,
            )
        if command.dry_run:
            return RuntimeCommandResult(
                workflow_id=command.workflow_id,
                action=command.action,
                executed=False,
                dry_run=True,
                authorized=True,
                requires_human_approval=False,
                request_id=command.request_id,
                reason="dry run only; no runtime mutation performed",
                event_payload=command.payload,
            )
        if command.action in self.READ_ONLY_ACTIONS:
            return RuntimeCommandResult(
                workflow_id=command.workflow_id,
                action=command.action,
                executed=False,
                dry_run=False,
                authorized=True,
                requires_human_approval=False,
                request_id=command.request_id,
                reason="observe action is read-only",
                event_payload=command.payload,
            )
        if command.action not in self.STATE_ACTIONS:
            return RuntimeCommandResult(
                workflow_id=command.workflow_id,
                action=command.action,
                executed=False,
                dry_run=False,
                authorized=True,
                requires_human_approval=False,
                request_id=command.request_id,
                reason=f"runtime adapter does not execute action {command.action.value}; host runtime must handle it",
                event_payload=command.payload,
            )
        event = kernel.intervene(
            command.workflow_id,
            command.action,
            command.subject,
            command.reason,
            command.payload,
        )
        return RuntimeCommandResult(
            workflow_id=command.workflow_id,
            action=command.action,
            executed=True,
            dry_run=False,
            authorized=True,
            requires_human_approval=False,
            request_id=command.request_id,
            reason="executed through kernel runtime boundary",
            event_payload={"event": event},
        )
