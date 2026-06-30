from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


def _json_default(obj: Any):
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)


class AuditEventType(StrEnum):
    GOVERNANCE_DECISION = "governance_decision"
    EDGE_DECISION = "edge_decision"
    WORKFLOW_DECISION = "workflow_decision"
    MAESTRO_EVENT = "maestro_event"
    ADAPTIVE_CHECKPOINT = "adaptive_checkpoint"
    DECISION_OUTCOME = "decision_outcome"
    POLICY_CRITIQUE = "policy_critique"
    POLICY_PATCH = "policy_patch"
    POLICY_ROLLBACK = "policy_rollback"
    DRIFT_ALERT = "drift_alert"
    HANDOFF_SCHEMA_ADVICE = "handoff_schema_advice"
    ADAPTIVE_CYCLE = "adaptive_cycle"
    METRICS_SNAPSHOT = "metrics_snapshot"
    BUDGET_GUARD = "budget_guard"
    REPLAY_COMPARISON = "replay_comparison"
    STRATEGY_SUGGESTION = "strategy_suggestion"
    ADAPTIVE_REVIEW = "adaptive_review"
    HUMAN_APPROVAL_REQUEST = "human_approval_request"
    WORKFLOW_HISTORY_EVENT = "workflow_history_event"
    ADAPTIVE_QUALITY_GATE = "adaptive_quality_gate"
    RUNTIME_INVARIANT = "runtime_invariant"
    HANDOFF_REPAIR_PLAN = "handoff_repair_plan"
    REPLAY_SCENARIO = "replay_scenario"
    ADAPTIVE_MODE_TRANSITION = "adaptive_mode_transition"
    PATCH_VERIFICATION = "patch_verification"
    ADAPTIVE_EVIDENCE_PACK = "adaptive_evidence_pack"
    OPERATING_CONTRACT = "operating_contract"
    OPERATING_CONTRACT_VALIDATION = "operating_contract_validation"
    RECOVERY_PLAYBOOK = "recovery_playbook"
    EVIDENCE_PACK_VALIDATION = "evidence_pack_validation"
    ADAPTIVE_CONVERGENCE = "adaptive_convergence"
    ADAPTIVE_INTEGRITY = "adaptive_integrity"
    ADAPTIVE_CERTIFICATION = "adaptive_certification"
    ACTION_AUTHORIZATION = "action_authorization"
    CHECKPOINT_SCHEDULE_DECISION = "checkpoint_schedule_decision"
    RUNTIME_COMMAND = "runtime_command"
    AUTO_OUTCOME_REPORT = "auto_outcome_report"
    CHECKPOINT_COALESCING_DECISION = "checkpoint_coalescing_decision"
    RUNTIME_COMMAND_DEDUPLICATION = "runtime_command_deduplication"
    ADAPTIVE_EFFICIENCY_REPORT = "adaptive_efficiency_report"
    CHECKPOINT_BACKPRESSURE_HINT = "checkpoint_backpressure_hint"
    RUNTIME_COMMAND_BATCH_PLAN = "runtime_command_batch_plan"
    OUTCOME_SWEEP_PLAN = "outcome_sweep_plan"
    ADAPTIVE_WORKLOAD_BUDGET_DECISION = "adaptive_workload_budget_decision"
    RUNTIME_COMMAND_CONFLICT_PLAN = "runtime_command_conflict_plan"
    ADAPTIVE_EVIDENCE_DIGEST = "adaptive_evidence_digest"
    RUNTIME_COMMAND_THROTTLE_PLAN = "runtime_command_throttle_plan"
    ADAPTIVE_EVIDENCE_DELTA = "adaptive_evidence_delta"
    ADAPTIVE_REPORT_ENCRYPTION = "adaptive_report_encryption"
    ADAPTIVE_REPORT_DECRYPTION = "adaptive_report_decryption"
    ADAPTIVE_ENCRYPTED_REPORT_INDEX = "adaptive_encrypted_report_index"
    ADAPTIVE_UI_SNAPSHOT = "adaptive_ui_snapshot"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Stable JSONL audit envelope used by the kernel and adaptive toolkit.

    The payload remains intentionally generic so existing dataclasses can be preserved while every emitted line
    includes a uniform event id, event type, subject, timestamp, policy version, and decision id when available.
    """

    event_type: AuditEventType
    subject_id: str
    payload: dict[str, Any]
    policy_version: str = "unversioned"
    decision_id: str | None = None
    event_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex}")
    created_at: float = field(default_factory=time.time)


def _payload_dict(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        return dict(event)
    if is_dataclass(event):
        return asdict(event)
    return {"repr": repr(event)}


def normalize_audit_event(event: Any) -> AuditEvent:
    """Wrap arbitrary kernel/adaptive events in a consistent audit envelope."""

    if isinstance(event, AuditEvent):
        return event

    payload = _payload_dict(event)
    class_name = event.__class__.__name__ if not isinstance(event, dict) else str(event.get("event_type", "unknown"))

    if class_name == "GovernanceDecision":
        event_type = AuditEventType.GOVERNANCE_DECISION
        subject_id = str(payload.get("agent_id", "unknown"))
    elif class_name == "EdgeDecision":
        event_type = AuditEventType.EDGE_DECISION
        subject_id = str(payload.get("edge_id", "unknown"))
    elif class_name == "WorkflowDecision":
        event_type = AuditEventType.WORKFLOW_DECISION
        subject_id = str(payload.get("workflow_id", "unknown"))
    elif class_name == "MaestroEvent":
        event_type = AuditEventType.MAESTRO_EVENT
        subject_id = str(payload.get("subject", payload.get("workflow_id", "unknown")))
    else:
        value = payload.get("event_type")
        try:
            event_type = AuditEventType(value)
        except (TypeError, ValueError):
            event_type = AuditEventType.UNKNOWN
        subject_id = str(payload.get("subject_id", payload.get("workflow_id", payload.get("decision_id", "unknown"))))

    return AuditEvent(
        event_type=event_type,
        subject_id=subject_id,
        payload=payload,
        policy_version=str(payload.get("policy_version", "unversioned")),
        decision_id=payload.get("decision_id"),
        created_at=float(payload.get("created_at", time.time()) or time.time()),
    )


class JsonlAuditSink:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: Any) -> None:
        envelope = normalize_audit_event(event)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(envelope, ensure_ascii=False, default=_json_default) + "\n")
