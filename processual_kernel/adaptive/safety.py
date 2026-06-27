from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ..adaptive_types import PolicyPatch, PolicyProfile, RiskLevel, RuntimeMode, TaskProfile
from ..types import MaestroAction

RISKY_AUTO_ACTIONS = {
    MaestroAction.ARCHIVE,
    MaestroAction.QUARANTINE,
    MaestroAction.REACTIVATE,
    MaestroAction.REROUTE,
}


@dataclass(slots=True)
class HumanApprovalRequest:
    request_id: str
    workflow_id: str
    action: str
    reason: str
    policy_version: str
    required: bool = True
    approved: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    decided_at: float | None = None


class AdaptiveSafetyGuard:
    """Central human-gate and auto-application safety checks for adaptive governance."""

    def __init__(self):
        self.requests: dict[str, HumanApprovalRequest] = {}

    def request_approval(
        self,
        workflow_id: str,
        action: str | MaestroAction,
        reason: str,
        policy_version: str,
        **metadata: Any,
    ) -> HumanApprovalRequest:
        action_value = action.value if isinstance(action, MaestroAction) else str(action)
        request = HumanApprovalRequest(
            request_id=f"approval_{uuid.uuid4().hex}",
            workflow_id=workflow_id,
            action=action_value,
            reason=reason,
            policy_version=policy_version,
            metadata=dict(metadata),
        )
        self.requests[request.request_id] = request
        return request

    def approve(self, request_id: str) -> HumanApprovalRequest:
        request = self.requests[request_id]
        request.approved = True
        request.decided_at = time.time()
        return request

    def pending(self, workflow_id: str | None = None) -> tuple[HumanApprovalRequest, ...]:
        values = self.requests.values()
        if workflow_id is not None:
            values = [r for r in values if r.workflow_id == workflow_id]
        return tuple(r for r in values if r.required and not r.approved)

    def requires_human_gate(
        self, profile: TaskProfile, policy: PolicyProfile, action: MaestroAction | None = None
    ) -> bool:
        if profile.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return True
        if policy.runtime_mode == RuntimeMode.RESTRICTED_CRITICAL or policy.human_gate_required:
            return True
        if action in RISKY_AUTO_ACTIONS:
            return True
        return False

    def can_auto_apply_patch(
        self, profile: TaskProfile, policy: PolicyProfile, patch: PolicyPatch, toolkit_mode: RuntimeMode
    ) -> bool:
        if toolkit_mode != RuntimeMode.CONTROLLED_ADAPTIVE:
            return False
        if policy.runtime_mode in {RuntimeMode.RESTRICTED_CRITICAL, RuntimeMode.OBSERVE}:
            return False
        if self.requires_human_gate(profile, policy):
            return False
        if patch.sample_size < policy.min_sample_size:
            return False
        return True
