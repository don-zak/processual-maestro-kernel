from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..adaptive_types import (
    AdaptiveEvidencePack,
    AdaptiveQualityGateReport,
    EvidencePackValidationResult,
    OperatingContract,
    OperatingContractValidation,
    PolicyPatch,
    PolicyProfile,
    RecoveryPlaybook,
    RecoveryPlaybookStep,
    RiskLevel,
    RuntimeInvariantReport,
    RuntimeMode,
    TaskProfile,
    TempoPlan,
)
from ..types import MaestroAction
from .calibrator import FORBIDDEN_FIELDS


class AdaptiveOperatingContractManager:
    """Builds and validates explicit operating contracts for adaptive governance.

    Contracts are a runtime safety boundary around the kernel. They do not mutate core state; they describe what the
    adaptive layer may recommend or apply, what must remain human-gated, and what evidence is required before expansion.
    """

    REQUIRED_EVIDENCE_ARTIFACTS = (
        "profile",
        "policy",
        "tempo",
        "metrics",
        "quality_gate",
        "runtime_invariants",
        "checkpoints",
        "policy_patches",
        "history",
    )

    def build_contract(
        self, workflow_id: str, profile: TaskProfile, policy: PolicyProfile, tempo: TempoPlan
    ) -> OperatingContract:
        human_gate_actions = [
            MaestroAction.ARCHIVE,
            MaestroAction.QUARANTINE,
            MaestroAction.REACTIVATE,
            MaestroAction.REROUTE,
        ]
        if profile.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} or policy.human_gate_required:
            human_gate_actions.extend([MaestroAction.ESCALATE, MaestroAction.PAUSE])

        allowed_actions = tuple(
            action for action in MaestroAction if action != MaestroAction.ARCHIVE or profile.risk != RiskLevel.CRITICAL
        )
        return OperatingContract(
            workflow_id=workflow_id,
            runtime_mode=policy.runtime_mode,
            policy_name=policy.name,
            policy_version=policy.policy_version,
            allowed_actions=allowed_actions,
            human_gate_actions=tuple(dict.fromkeys(human_gate_actions)),
            forbidden_patch_fields=tuple(sorted(FORBIDDEN_FIELDS)),
            checkpoint_interval_minutes=tempo.checkpoint_interval_minutes,
            audit_required=profile.requires_audit,
            min_outcome_coverage=0.98 if profile.risk == RiskLevel.CRITICAL else 0.95,
            max_pending_outcomes=0,
            max_pending_approvals=0,
            critical_mode_locked=profile.risk == RiskLevel.CRITICAL,
        )

    def validate(
        self,
        contract: OperatingContract,
        quality_gate: AdaptiveQualityGateReport | None = None,
        runtime_invariants: RuntimeInvariantReport | None = None,
        pending_outcome_count: int = 0,
        pending_approval_count: int = 0,
        requested_action: MaestroAction | None = None,
        requested_patch: PolicyPatch | None = None,
        auto_apply_requested: bool = False,
    ) -> OperatingContractValidation:
        violations: list[str] = []
        warnings: list[str] = []

        if contract.audit_required is False:
            warnings.append("audit is disabled for this contract; adaptive evidence will be weaker")
        if quality_gate is not None:
            if quality_gate.metrics and quality_gate.metrics.outcome_coverage_ratio < contract.min_outcome_coverage:
                violations.append(
                    f"outcome coverage {quality_gate.metrics.outcome_coverage_ratio:.2f} "
                    f"below contract minimum {contract.min_outcome_coverage:.2f}"
                )
            if not quality_gate.passed and auto_apply_requested:
                violations.append("auto-apply requested while quality gate has not passed")
        if runtime_invariants is not None and not runtime_invariants.passed:
            violations.extend(f"runtime invariant: {item}" for item in runtime_invariants.violations)
        if pending_outcome_count > contract.max_pending_outcomes:
            violations.append(
                f"{pending_outcome_count} pending outcomes exceed contract limit {contract.max_pending_outcomes}"
            )
        if pending_approval_count > contract.max_pending_approvals:
            violations.append(
                f"{pending_approval_count} pending approvals exceed contract limit {contract.max_pending_approvals}"
            )
        if requested_action is not None:
            if requested_action not in contract.allowed_actions:
                violations.append(f"action {requested_action.value} is not allowed by operating contract")
            if auto_apply_requested and requested_action in contract.human_gate_actions:
                violations.append(f"action {requested_action.value} requires human approval")
        if requested_patch is not None:
            if requested_patch.field in contract.forbidden_patch_fields:
                violations.append(f"patch field {requested_patch.field} is forbidden by operating contract")
            if auto_apply_requested and contract.runtime_mode != RuntimeMode.CONTROLLED_ADAPTIVE:
                violations.append("patch auto-apply requires controlled adaptive runtime mode")
        if contract.critical_mode_locked and contract.runtime_mode != RuntimeMode.RESTRICTED_CRITICAL:
            violations.append("critical workflow contract must remain in restricted critical runtime mode")

        return OperatingContractValidation(
            workflow_id=contract.workflow_id,
            contract=contract,
            passed=not violations,
            violations=tuple(dict.fromkeys(violations)),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def build_recovery_playbook(
        self,
        workflow_id: str,
        findings: Iterable[str] = (),
        violations: Iterable[str] = (),
        handoff_repairs: Iterable[Any] = (),
        pending_outcome_count: int = 0,
        pending_approval_count: int = 0,
    ) -> RecoveryPlaybook:
        steps: list[RecoveryPlaybookStep] = []
        priority = 1
        if pending_approval_count:
            steps.append(
                RecoveryPlaybookStep(
                    step_id=f"rp_{priority:02d}",
                    action="resolve_human_approvals",
                    reason=f"{pending_approval_count} pending human approval request(s)",
                    priority=priority,
                    requires_human_approval=True,
                    expected_effect="unblock safe adaptive transitions",
                    source="safety_guard",
                )
            )
            priority += 1
        if pending_outcome_count:
            steps.append(
                RecoveryPlaybookStep(
                    step_id=f"rp_{priority:02d}",
                    action="collect_missing_outcomes",
                    reason=f"{pending_outcome_count} important decision outcome(s) missing",
                    priority=priority,
                    expected_effect="improve policy critique and calibration evidence",
                    source="decision_ledger",
                )
            )
            priority += 1
        for item in violations:
            steps.append(
                RecoveryPlaybookStep(
                    step_id=f"rp_{priority:02d}",
                    action="repair_runtime_invariant",
                    reason=str(item),
                    priority=priority,
                    requires_human_approval="critical" in str(item).lower() or "approval" in str(item).lower(),
                    expected_effect="restore operating contract compliance",
                    source="runtime_invariants",
                )
            )
            priority += 1
        for repair in handoff_repairs:
            edge_id = getattr(repair, "edge_id", "handoff")
            steps.append(
                RecoveryPlaybookStep(
                    step_id=f"rp_{priority:02d}",
                    action="execute_handoff_repair",
                    reason=f"repair weak handoff {edge_id}",
                    priority=priority,
                    requires_human_approval=bool(getattr(repair, "human_review_required", False)),
                    expected_effect=getattr(repair, "expected_effect", "improve handoff quality"),
                    source="handoff_advisor",
                )
            )
            priority += 1
        for finding in findings:
            if "retry" in finding.lower() or "handoff" in finding.lower() or "escalat" in finding.lower():
                steps.append(
                    RecoveryPlaybookStep(
                        step_id=f"rp_{priority:02d}",
                        action="review_policy_finding",
                        reason=str(finding),
                        priority=priority,
                        expected_effect="convert critique into an auditable policy decision",
                        source="policy_critic",
                    )
                )
                priority += 1
        if not steps:
            steps.append(
                RecoveryPlaybookStep(
                    step_id="rp_01",
                    action="continue_observing",
                    reason="no recovery action required by current adaptive evidence",
                    priority=1,
                    expected_effect="maintain stable governance without unnecessary intervention",
                )
            )
        confidence = min(0.95, 0.55 + 0.05 * min(6, len(steps)))
        return RecoveryPlaybook(workflow_id=workflow_id, steps=tuple(steps), confidence=round(confidence, 4))

    def validate_evidence_pack(self, pack: AdaptiveEvidencePack) -> EvidencePackValidationResult:
        artifacts = pack.artifacts or {}
        missing = [
            name for name in self.REQUIRED_EVIDENCE_ARTIFACTS if name not in artifacts or artifacts.get(name) is None
        ]
        mismatches: list[str] = []
        for key, artifact_key in (
            ("checkpoints", "checkpoints"),
            ("drift_alerts", "drift_alerts"),
            ("handoff_suggestions", "handoff_suggestions"),
            ("policy_critiques", "policy_critiques"),
            ("policy_patches", "policy_patches"),
            ("approvals", "approvals"),
            ("history_events", "history"),
            ("replay_results", "replay_results"),
            ("runtime_commands", "runtime_commands"),
            ("auto_outcome_reports", "auto_outcome_reports"),
            ("checkpoint_coalescing", "checkpoint_coalescing"),
            ("runtime_deduplication", "runtime_deduplication"),
            ("efficiency_reports", "efficiency_reports"),
            ("checkpoint_backpressure", "checkpoint_backpressure"),
            ("runtime_batches", "runtime_batches"),
            ("outcome_sweep_plans", "outcome_sweep_plans"),
            ("workload_budget_decisions", "workload_budget_decisions"),
            ("runtime_conflicts", "runtime_conflicts"),
            ("evidence_digests", "evidence_digests"),
            ("runtime_throttles", "runtime_throttles"),
            ("evidence_deltas", "evidence_deltas"),
            ("encrypted_reports", "encrypted_reports"),
        ):
            expected = pack.counts.get(key)
            actual_value = artifacts.get(artifact_key, [])
            actual = len(actual_value) if isinstance(actual_value, list) else 0
            if expected is not None and expected != actual:
                mismatches.append(f"{key}: count={expected}, artifact_len={actual}")
        warnings: list[str] = []
        if not pack.schema_version.startswith("adaptive-evidence-pack-"):
            warnings.append("unknown evidence pack schema namespace")
        if pack.schema_version != "adaptive-evidence-pack-1.7.0":
            warnings.append(f"schema version {pack.schema_version} is not the current 1.7.0 schema")
        return EvidencePackValidationResult(
            workflow_id=pack.workflow_id,
            schema_version=pack.schema_version,
            valid=not missing and not mismatches,
            missing_artifacts=tuple(missing),
            count_mismatches=tuple(mismatches),
            warnings=tuple(warnings),
        )
