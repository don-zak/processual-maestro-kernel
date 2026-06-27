from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ..adaptive_types import (
    AdaptiveEvidencePack,
    AdaptiveModeTransitionDecision,
    AdaptiveQualityGateReport,
    MetricsSnapshot,
    PatchVerificationResult,
    PolicyPatch,
    RiskLevel,
    RuntimeInvariantReport,
    RuntimeMode,
    TaskProfile,
)


def _safe_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_safe_dict(item) for item in value]
    if isinstance(value, list):
        return [_safe_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _safe_dict(v) for k, v in value.items()}
    return value


class AdaptiveOperationsGovernor:
    """Read-only operational governance for runtime promotion, patch verification, and evidence packs.

    This layer deliberately sits outside the core kernel. It never changes Ψ equations or cgtlib behavior.
    Runtime mode changes and rollbacks are performed only by the toolkit after this governor returns evidence.
    """

    def decide_mode_transition(
        self,
        workflow_id: str,
        current_mode: RuntimeMode,
        requested_mode: RuntimeMode,
        profile: TaskProfile,
        quality_gate: AdaptiveQualityGateReport,
        runtime_invariants: RuntimeInvariantReport,
        metrics: MetricsSnapshot,
        pending_outcome_count: int,
        pending_approval_count: int,
    ) -> AdaptiveModeTransitionDecision:
        violations: list[str] = []
        warnings: list[str] = []
        required_human_approval = False

        if requested_mode == current_mode:
            warnings.append("requested runtime mode is already active")

        if profile.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            required_human_approval = True
            if requested_mode == RuntimeMode.CONTROLLED_ADAPTIVE:
                violations.append(
                    "high/critical workflows cannot be promoted to controlled adaptive mode automatically"
                )

        if profile.risk == RiskLevel.CRITICAL and requested_mode != RuntimeMode.RESTRICTED_CRITICAL:
            violations.append("critical workflows must remain in restricted critical mode")

        if requested_mode == RuntimeMode.CONTROLLED_ADAPTIVE:
            if not quality_gate.passed:
                violations.extend(f"quality gate: {item}" for item in quality_gate.violations)
            if not runtime_invariants.passed:
                violations.extend(f"runtime invariant: {item}" for item in runtime_invariants.violations)
            if pending_outcome_count:
                violations.append("all important decisions need outcomes before controlled adaptation")
            if pending_approval_count:
                violations.append("pending human approvals must be resolved before controlled adaptation")

        if requested_mode == RuntimeMode.RECOMMEND and current_mode == RuntimeMode.OBSERVE:
            if metrics.workflow_count == 0:
                warnings.append("promotion to recommend has no workflow evidence yet")
            if pending_approval_count:
                violations.append("pending human approvals must be resolved before promotion")

        if requested_mode == RuntimeMode.OBSERVE and current_mode == RuntimeMode.CONTROLLED_ADAPTIVE:
            warnings.append("demotion to observe is safe and should be preferred after regressions")

        if metrics.policy_patch_success_rate < 0.5 and requested_mode == RuntimeMode.CONTROLLED_ADAPTIVE:
            violations.append("policy patch success rate is too low for controlled adaptation")

        allowed = not violations and not required_human_approval
        if required_human_approval and not violations:
            warnings.append("human approval is required before applying this transition")

        reason = "transition allowed" if allowed else "transition blocked by safety evidence"
        if required_human_approval and not violations:
            reason = "transition requires human approval"

        return AdaptiveModeTransitionDecision(
            workflow_id=workflow_id,
            current_mode=current_mode,
            requested_mode=requested_mode,
            allowed=allowed,
            reason=reason,
            quality_gate=quality_gate,
            runtime_invariants=runtime_invariants,
            pending_outcome_count=pending_outcome_count,
            pending_approval_count=pending_approval_count,
            required_human_approval=required_human_approval,
            violations=tuple(dict.fromkeys(violations)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def verify_patches(
        self,
        workflow_id: str,
        patches: Iterable[PolicyPatch],
        metrics: MetricsSnapshot,
        recent_decision_quality: float | None = None,
        min_decision_quality: float = 0.55,
    ) -> tuple[PatchVerificationResult, ...]:
        results: list[PatchVerificationResult] = []
        for patch in patches:
            regressions: list[str] = []
            confidence = 0.55
            if recent_decision_quality is not None:
                confidence = max(0.35, min(0.95, recent_decision_quality))
                if recent_decision_quality < min_decision_quality:
                    regressions.append(
                        f"recent decision quality {recent_decision_quality:.2f} below {min_decision_quality:.2f}"
                    )
            if metrics.false_retry_rate > 0.30:
                regressions.append(f"false retry rate {metrics.false_retry_rate:.2f} above 0.30")
            if metrics.false_reroute_rate > 0.30:
                regressions.append(f"false reroute rate {metrics.false_reroute_rate:.2f} above 0.30")
            if metrics.handoff_failure_rate > 0.45:
                regressions.append(f"handoff failure rate {metrics.handoff_failure_rate:.2f} above 0.45")
            if metrics.outcome_coverage_ratio < 0.80:
                regressions.append(f"outcome coverage {metrics.outcome_coverage_ratio:.2f} below 0.80")

            rollback_recommended = bool(regressions) and patch.reversible
            if not regressions and metrics.policy_patch_success_rate >= 0.80:
                status = "verified"
                reason = "post-patch evidence remains within safety limits"
            elif rollback_recommended:
                status = "rollback_recommended"
                reason = "; ".join(regressions)
            else:
                status = "needs_more_evidence"
                reason = "insufficient or mixed evidence; keep observing without further expansion"

            results.append(
                PatchVerificationResult(
                    workflow_id=workflow_id,
                    patch=patch,
                    status=status,
                    rollback_recommended=rollback_recommended,
                    reason=reason,
                    metrics=metrics,
                    confidence=round(confidence, 4),
                )
            )
        return tuple(results)

    def build_evidence_pack(
        self,
        workflow_id: str,
        profile: Any,
        policy: Any,
        tempo: Any,
        metrics: MetricsSnapshot,
        quality_gate: AdaptiveQualityGateReport,
        runtime_invariants: RuntimeInvariantReport,
        checkpoints: Iterable[Any] = (),
        drift_alerts: Iterable[Any] = (),
        handoff_suggestions: Iterable[Any] = (),
        policy_critiques: Iterable[Any] = (),
        policy_patches: Iterable[Any] = (),
        approvals: Iterable[Any] = (),
        history: Iterable[Any] = (),
        replay_results: Iterable[Any] = (),
        transition_decision: AdaptiveModeTransitionDecision | None = None,
        operating_contract: Any = None,
        contract_validation: Any = None,
        convergence_report: Any = None,
        recovery_playbook: Any = None,
        evidence_pack_validation: Any = None,
        runtime_commands: Iterable[Any] = (),
        auto_outcome_reports: Iterable[Any] = (),
        checkpoint_coalescing: Iterable[Any] = (),
        runtime_deduplication: Iterable[Any] = (),
        efficiency_reports: Iterable[Any] = (),
        checkpoint_backpressure: Iterable[Any] = (),
        runtime_batches: Iterable[Any] = (),
        outcome_sweep_plans: Iterable[Any] = (),
        workload_budget_decisions: Iterable[Any] = (),
        runtime_conflicts: Iterable[Any] = (),
        evidence_digests: Iterable[Any] = (),
        runtime_throttles: Iterable[Any] = (),
        evidence_deltas: Iterable[Any] = (),
        encrypted_reports: Iterable[Any] = (),
        encrypted_report_indexes: Iterable[Any] = (),
        ui_snapshots: Iterable[Any] = (),
    ) -> AdaptiveEvidencePack:
        checkpoint_items = tuple(checkpoints)
        drift_items = tuple(drift_alerts)
        handoff_items = tuple(handoff_suggestions)
        critique_items = tuple(policy_critiques)
        patch_items = tuple(policy_patches)
        approval_items = tuple(approvals)
        history_items = tuple(history)
        replay_items = tuple(replay_results)
        runtime_command_items = tuple(runtime_commands)
        auto_outcome_items = tuple(auto_outcome_reports)
        checkpoint_coalescing_items = tuple(checkpoint_coalescing)
        runtime_deduplication_items = tuple(runtime_deduplication)
        efficiency_report_items = tuple(efficiency_reports)
        checkpoint_backpressure_items = tuple(checkpoint_backpressure)
        runtime_batch_items = tuple(runtime_batches)
        outcome_sweep_plan_items = tuple(outcome_sweep_plans)
        workload_budget_items = tuple(workload_budget_decisions)
        runtime_conflict_items = tuple(runtime_conflicts)
        evidence_digest_items = tuple(evidence_digests)
        runtime_throttle_items = tuple(runtime_throttles)
        evidence_delta_items = tuple(evidence_deltas)
        encrypted_report_items = tuple(encrypted_reports)
        encrypted_report_index_items = tuple(encrypted_report_indexes)
        ui_snapshot_items = tuple(ui_snapshots)
        counts = {
            "checkpoints": len(checkpoint_items),
            "drift_alerts": len(drift_items),
            "handoff_suggestions": len(handoff_items),
            "policy_critiques": len(critique_items),
            "policy_patches": len(patch_items),
            "approvals": len(approval_items),
            "history_events": len(history_items),
            "replay_results": len(replay_items),
            "operating_contracts": 1 if operating_contract is not None else 0,
            "contract_validations": 1 if contract_validation is not None else 0,
            "convergence_reports": 1 if convergence_report is not None else 0,
            "recovery_playbooks": 1 if recovery_playbook is not None else 0,
            "evidence_pack_validations": 1 if evidence_pack_validation is not None else 0,
            "runtime_commands": len(runtime_command_items),
            "auto_outcome_reports": len(auto_outcome_items),
            "checkpoint_coalescing": len(checkpoint_coalescing_items),
            "runtime_deduplication": len(runtime_deduplication_items),
            "efficiency_reports": len(efficiency_report_items),
            "checkpoint_backpressure": len(checkpoint_backpressure_items),
            "runtime_batches": len(runtime_batch_items),
            "outcome_sweep_plans": len(outcome_sweep_plan_items),
            "workload_budget_decisions": len(workload_budget_items),
            "runtime_conflicts": len(runtime_conflict_items),
            "evidence_digests": len(evidence_digest_items),
            "runtime_throttles": len(runtime_throttle_items),
            "evidence_deltas": len(evidence_delta_items),
            "encrypted_reports": len(encrypted_report_items),
            "encrypted_report_indexes": len(encrypted_report_index_items),
            "ui_snapshots": len(ui_snapshot_items),
        }
        artifacts = {
            "profile": _safe_dict(profile),
            "policy": _safe_dict(policy),
            "tempo": _safe_dict(tempo),
            "metrics": _safe_dict(metrics),
            "quality_gate": _safe_dict(quality_gate),
            "runtime_invariants": _safe_dict(runtime_invariants),
            "checkpoints": _safe_dict(checkpoint_items),
            "drift_alerts": _safe_dict(drift_items),
            "handoff_suggestions": _safe_dict(handoff_items),
            "policy_critiques": _safe_dict(critique_items),
            "policy_patches": _safe_dict(patch_items),
            "approvals": _safe_dict(approval_items),
            "history": _safe_dict(history_items),
            "replay_results": _safe_dict(replay_items),
            "transition_decision": _safe_dict(transition_decision) if transition_decision is not None else None,
            "operating_contract": _safe_dict(operating_contract) if operating_contract is not None else None,
            "contract_validation": _safe_dict(contract_validation) if contract_validation is not None else None,
            "convergence_report": _safe_dict(convergence_report) if convergence_report is not None else None,
            "recovery_playbook": _safe_dict(recovery_playbook) if recovery_playbook is not None else None,
            "evidence_pack_validation": _safe_dict(evidence_pack_validation)
            if evidence_pack_validation is not None
            else None,
            "runtime_commands": _safe_dict(runtime_command_items),
            "auto_outcome_reports": _safe_dict(auto_outcome_items),
            "checkpoint_coalescing": _safe_dict(checkpoint_coalescing_items),
            "runtime_deduplication": _safe_dict(runtime_deduplication_items),
            "efficiency_reports": _safe_dict(efficiency_report_items),
            "checkpoint_backpressure": _safe_dict(checkpoint_backpressure_items),
            "runtime_batches": _safe_dict(runtime_batch_items),
            "outcome_sweep_plans": _safe_dict(outcome_sweep_plan_items),
            "workload_budget_decisions": _safe_dict(workload_budget_items),
            "runtime_conflicts": _safe_dict(runtime_conflict_items),
            "evidence_digests": _safe_dict(evidence_digest_items),
            "runtime_throttles": _safe_dict(runtime_throttle_items),
            "evidence_deltas": _safe_dict(evidence_delta_items),
            "encrypted_reports": _safe_dict(encrypted_report_items),
            "encrypted_report_indexes": _safe_dict(encrypted_report_index_items),
            "ui_snapshots": _safe_dict(ui_snapshot_items),
        }
        return AdaptiveEvidencePack(
            workflow_id=workflow_id,
            counts=counts,
            artifacts=artifacts,
        )

    @staticmethod
    def write_evidence_pack(pack: AdaptiveEvidencePack, path: str | Path) -> Path:
        import json

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(_safe_dict(pack), ensure_ascii=False, indent=2), encoding="utf-8")
        return target
