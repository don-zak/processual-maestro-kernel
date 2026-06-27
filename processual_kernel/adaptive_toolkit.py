from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .adaptive.calibrator import CalibrationEngine
from .adaptive.certification import AdaptiveCertificationAuthority
from .adaptive.checkpoint_controller import CheckpointScheduleController
from .adaptive.checkpoints import CheckpointScheduler
from .adaptive.contracts import AdaptiveOperatingContractManager
from .adaptive.convergence import AdaptiveConvergenceMonitor
from .adaptive.drift_detector import DriftDetector
from .adaptive.efficiency import AdaptiveEfficiencyGovernor
from .adaptive.encryption import AdaptiveReportEncryptor
from .adaptive.handoff_advisor import HandoffSchemaAdvisor
from .adaptive.history import WorkflowHistoryRecorder
from .adaptive.ledger import DecisionLedger, DecisionLedgerEntry
from .adaptive.metrics import AdaptiveMetricsCollector
from .adaptive.ops_governance import AdaptiveOperationsGovernor
from .adaptive.outcome_evaluator import OutcomeEvaluator
from .adaptive.persistence import AdaptiveJsonStore
from .adaptive.policy_critic import PolicyCritic
from .adaptive.policy_selector import PolicySelector
from .adaptive.quality_gates import AdaptiveQualityGate
from .adaptive.replay_lab import ReplayLab
from .adaptive.runtime_adapter import AdaptiveRuntimeAdapter
from .adaptive.safety import AdaptiveSafetyGuard, HumanApprovalRequest
from .adaptive.strategy_bandit import StrategyBandit
from .adaptive.task_profiler import TaskProfiler
from .adaptive.tempo_controller import TempoController
from .adaptive.ui import build_adaptive_dashboard_html, write_adaptive_dashboard_html
from .adaptive_types import (
    ActionAuthorizationReport,
    AdaptiveCertificationReport,
    AdaptiveConvergenceReport,
    AdaptiveCycleReport,
    AdaptiveEfficiencyReport,
    AdaptiveEncryptedReportIndex,
    AdaptiveEvidenceDelta,
    AdaptiveEvidenceDigest,
    AdaptiveEvidencePack,
    AdaptiveIntegrityReport,
    AdaptiveModeTransitionDecision,
    AdaptiveQualityGateReport,
    AdaptiveReportDecryptionResult,
    AdaptiveReviewReport,
    AdaptiveUiSnapshot,
    AdaptiveWorkloadBudgetDecision,
    AutoOutcomeReport,
    CheckpointBackpressureHint,
    CheckpointCoalescingDecision,
    CheckpointReport,
    CheckpointScheduleDecision,
    CounterfactualReplayResult,
    DecisionOutcome,
    DriftAlert,
    EncryptedAdaptiveReport,
    EvidencePackValidationResult,
    HandoffRepairPlan,
    HandoffSchemaSuggestion,
    HandoffValidationResult,
    MetricsSnapshot,
    OperatingContract,
    OperatingContractValidation,
    OutcomeSweepPlan,
    PatchVerificationResult,
    PolicyCritique,
    PolicyPatch,
    PolicyPatchHistoryEntry,
    PolicyProfile,
    RecoveryPlaybook,
    ReplayComparison,
    RuntimeCommand,
    RuntimeCommandBatchPlan,
    RuntimeCommandConflictPlan,
    RuntimeCommandDeduplicationResult,
    RuntimeCommandResult,
    RuntimeCommandThrottlePlan,
    RuntimeInvariantReport,
    RuntimeMode,
    TaskProfile,
    TempoPlan,
    WorkflowHistoryEvent,
)
from .audit import AuditEventType
from .types import (
    GovernanceDecision,
    MaestroAction,
    WorkflowPlan,
    WorkflowRecord,
    WorkflowState,
    WorkflowTelemetry,
)


class AdaptiveGovernanceToolkit:
    """Adaptive tools around ProcessualMaestroKernel.

    The toolkit profiles, reviews, critiques, and recommends. It does not rewrite Ψ equations or cgtlib internals.
    Policy application is explicit and versioned.
    """

    def __init__(self, kernel, mode: RuntimeMode = RuntimeMode.RECOMMEND, store_path: str | Path | None = None):
        self.kernel = kernel
        self.mode = mode
        self.profiler = TaskProfiler()
        self.selector = PolicySelector(kernel.policy)
        self.checkpoints = CheckpointScheduler()
        self.checkpoint_controller = CheckpointScheduleController()
        self.runtime_adapter = AdaptiveRuntimeAdapter()
        self.evaluator = OutcomeEvaluator()
        self.critic = PolicyCritic()
        self.calibrator = CalibrationEngine(mode=mode)
        self.tempo_controller = TempoController()
        self.drift_detector = DriftDetector()
        self.replay_lab = ReplayLab()
        self.strategy_bandit = StrategyBandit()
        self.handoff_advisor = HandoffSchemaAdvisor()
        self.metrics_collector = AdaptiveMetricsCollector()
        self.quality_gates = AdaptiveQualityGate()
        self.operations_governor = AdaptiveOperationsGovernor()
        self.efficiency_governor = AdaptiveEfficiencyGovernor()
        self.report_encryptor = AdaptiveReportEncryptor()
        self.contracts = AdaptiveOperatingContractManager()
        self.certifier = AdaptiveCertificationAuthority(self.contracts)
        self.convergence_monitor = AdaptiveConvergenceMonitor()
        self.ledger = DecisionLedger()
        self.history_recorder = WorkflowHistoryRecorder()
        self.safety_guard = AdaptiveSafetyGuard()
        self.store = AdaptiveJsonStore(store_path) if store_path is not None else None
        self._profiles: dict[str, TaskProfile] = {}
        self._policies: dict[str, PolicyProfile] = {}
        self._tempo_plans: dict[str, TempoPlan] = {}
        self._checkpoint_reports: dict[str, list[CheckpointReport]] = {}
        self._checkpoint_drift_alerts: dict[str, list[DriftAlert]] = {}
        self._checkpoint_handoff_suggestions: dict[str, list[HandoffSchemaSuggestion]] = {}
        self._checkpoint_critiques: dict[str, list[PolicyCritique]] = {}
        self._checkpoint_patches: dict[str, list[PolicyPatch]] = {}
        self._cycle_reports: list[AdaptiveCycleReport] = []
        self._operating_contracts: dict[str, OperatingContract] = {}
        self._contract_validations: dict[str, list[OperatingContractValidation]] = {}
        self._recovery_playbooks: dict[str, RecoveryPlaybook] = {}
        self._convergence_reports: dict[str, list[AdaptiveConvergenceReport]] = {}
        self._evidence_pack_validations: dict[str, list[EvidencePackValidationResult]] = {}
        self._successful_patch_versions: set[str] = set()
        self._runtime_command_results: dict[str, list[RuntimeCommandResult]] = {}
        self._auto_outcome_reports: dict[str, list[AutoOutcomeReport]] = {}
        self._checkpoint_schedule_decisions: dict[str, list[CheckpointScheduleDecision]] = {}
        self._checkpoint_coalescing_decisions: dict[str, list[CheckpointCoalescingDecision]] = {}
        self._checkpoint_backpressure_hints: dict[str, list[CheckpointBackpressureHint]] = {}
        self._runtime_deduplication_results: dict[str, list[RuntimeCommandDeduplicationResult]] = {}
        self._runtime_batch_plans: dict[str, list[RuntimeCommandBatchPlan]] = {}
        self._outcome_sweep_plans: dict[str, list[OutcomeSweepPlan]] = {}
        self._runtime_command_fingerprints: dict[str, set[str]] = {}
        self._efficiency_reports: dict[str, list[AdaptiveEfficiencyReport]] = {}
        self._workload_budget_decisions: dict[str, list[AdaptiveWorkloadBudgetDecision]] = {}
        self._runtime_conflict_plans: dict[str, list[RuntimeCommandConflictPlan]] = {}
        self._evidence_digests: dict[str, list[AdaptiveEvidenceDigest]] = {}
        self._runtime_throttle_plans: dict[str, list[RuntimeCommandThrottlePlan]] = {}
        self._evidence_deltas: dict[str, list[AdaptiveEvidenceDelta]] = {}
        self._encrypted_reports: dict[str, list[EncryptedAdaptiveReport]] = {}
        self._encrypted_report_indexes: dict[str, list[AdaptiveEncryptedReportIndex]] = {}
        self._ui_snapshots: dict[str, list[AdaptiveUiSnapshot]] = {}

    def _audit_adaptive(self, event_type: AuditEventType, subject_id: str, payload: dict) -> None:
        audit = getattr(self.kernel, "_audit", None)
        if callable(audit):
            audit(
                {
                    "event_type": event_type.value,
                    "subject_id": subject_id,
                    **payload,
                }
            )

    def _persist(self, kind: str, artifact) -> None:
        if self.store is not None:
            self.store.append(kind, artifact)

    def _record_history_event(self, event: WorkflowHistoryEvent) -> None:
        self._audit_adaptive(
            AuditEventType.WORKFLOW_HISTORY_EVENT,
            event.workflow_id,
            {
                "workflow_id": event.workflow_id,
                "event_type_name": event.event_type,
                "action": event.action.value if event.action else None,
                "payload": event,
            },
        )
        self._persist("workflow_history", event)

    def request_human_approval(
        self,
        workflow_id: str,
        action: str | MaestroAction,
        reason: str,
        policy_version: str | None = None,
        **metadata,
    ) -> HumanApprovalRequest:
        request = self.safety_guard.request_approval(
            workflow_id=workflow_id,
            action=action,
            reason=reason,
            policy_version=policy_version or getattr(self.kernel.policy, "policy_version", "unversioned"),
            **metadata,
        )
        self._audit_adaptive(
            AuditEventType.HUMAN_APPROVAL_REQUEST,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "request_id": request.request_id,
                "action": request.action,
                "reason": request.reason,
                "policy_version": request.policy_version,
                "payload": request,
            },
        )
        self._persist("human_approval_requests", request)
        return request

    def pending_approval_requests(self, workflow_id: str | None = None) -> tuple[HumanApprovalRequest, ...]:
        return self.safety_guard.pending(workflow_id=workflow_id)

    def approve_human_request(self, request_id: str) -> HumanApprovalRequest:
        request = self.safety_guard.approve(request_id)
        self._audit_adaptive(
            AuditEventType.HUMAN_APPROVAL_REQUEST,
            request.workflow_id,
            {
                "workflow_id": request.workflow_id,
                "request_id": request.request_id,
                "action": request.action,
                "approved": request.approved,
                "policy_version": request.policy_version,
                "payload": request,
            },
        )
        self._persist("human_approval_requests", request)
        return request

    def runtime_invariant_report(
        self,
        workflow_id: str,
        profile: TaskProfile | None = None,
        policy: PolicyProfile | None = None,
        auto_apply_requested: bool = False,
    ) -> RuntimeInvariantReport:
        profile = profile or self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = policy or self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        checked = (
            "critical workflows remain human gated",
            "restricted or observe policies do not auto-apply patches",
            "risky actions require human approval",
            "core/cgtlib settings are not modified by adaptive tools",
        )
        violations: list[str] = []
        warnings: list[str] = []
        if profile.risk.value in {"high", "critical"} and not self.safety_guard.requires_human_gate(profile, policy):
            violations.append("high/critical workflow is not protected by a human gate")
        if profile.risk.value == "critical" and policy.runtime_mode != RuntimeMode.RESTRICTED_CRITICAL:
            violations.append("critical workflow must use restricted critical runtime mode")
        if auto_apply_requested and policy.runtime_mode in {RuntimeMode.OBSERVE, RuntimeMode.RESTRICTED_CRITICAL}:
            violations.append("auto-apply requested under observe/restricted policy")
        if auto_apply_requested and self.safety_guard.requires_human_gate(profile, policy):
            violations.append("auto-apply requested while a human gate is required")
        if self.pending_outcomes() and self.mode == RuntimeMode.CONTROLLED_ADAPTIVE:
            warnings.append("controlled mode has pending decision outcomes; keep calibration conservative")

        report = RuntimeInvariantReport(
            workflow_id=workflow_id,
            passed=not violations,
            checked_invariants=checked,
            violations=tuple(violations),
            warnings=tuple(warnings),
        )
        self._audit_adaptive(
            AuditEventType.RUNTIME_INVARIANT,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "passed": report.passed,
                "violation_count": len(report.violations),
                "warning_count": len(report.warnings),
                "payload": report,
            },
        )
        self._persist("runtime_invariants", report)
        return report

    def operating_contract(
        self,
        workflow_id: str,
        profile: TaskProfile | None = None,
        policy: PolicyProfile | None = None,
        tempo: TempoPlan | None = None,
    ) -> OperatingContract:
        profile = profile or self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = policy or self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        tempo = tempo or self._tempo_plans.get(workflow_id) or self.plan_tempo(profile, policy, workflow_id=workflow_id)
        contract = self.contracts.build_contract(workflow_id, profile, policy, tempo)
        self._operating_contracts[workflow_id] = contract
        self._audit_adaptive(
            AuditEventType.OPERATING_CONTRACT,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "runtime_mode": contract.runtime_mode.value,
                "policy_version": contract.policy_version,
                "human_gate_action_count": len(contract.human_gate_actions),
                "forbidden_patch_field_count": len(contract.forbidden_patch_fields),
                "payload": contract,
            },
        )
        self._persist("operating_contracts", contract)
        return contract

    def validate_operating_contract(
        self,
        workflow_id: str,
        contract: OperatingContract | None = None,
        quality_gate: AdaptiveQualityGateReport | None = None,
        runtime_invariants: RuntimeInvariantReport | None = None,
        requested_action: MaestroAction | None = None,
        requested_patch: PolicyPatch | None = None,
        auto_apply_requested: bool = False,
    ) -> OperatingContractValidation:
        contract = contract or self._operating_contracts.get(workflow_id) or self.operating_contract(workflow_id)
        quality_gate = quality_gate or self.quality_gate_report(workflow_id)
        runtime_invariants = runtime_invariants or self.runtime_invariant_report(workflow_id)
        validation = self.contracts.validate(
            contract,
            quality_gate=quality_gate,
            runtime_invariants=runtime_invariants,
            pending_outcome_count=len(self.pending_outcomes()),
            pending_approval_count=len(self.pending_approval_requests(workflow_id)),
            requested_action=requested_action,
            requested_patch=requested_patch,
            auto_apply_requested=auto_apply_requested,
        )
        self._contract_validations.setdefault(workflow_id, []).append(validation)
        self._audit_adaptive(
            AuditEventType.OPERATING_CONTRACT_VALIDATION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "passed": validation.passed,
                "violation_count": len(validation.violations),
                "warning_count": len(validation.warnings),
                "payload": validation,
            },
        )
        self._persist("operating_contract_validations", validation)
        return validation

    def convergence_report(self, workflow_id: str) -> AdaptiveConvergenceReport:
        report = self.convergence_monitor.evaluate(workflow_id)
        self._convergence_reports.setdefault(workflow_id, []).append(report)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_CONVERGENCE,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "stable": report.stable,
                "window_size": report.window_size,
                "recommendation": report.recommendation,
                "payload": report,
            },
        )
        self._persist("adaptive_convergence", report)
        return report

    def build_recovery_playbook(
        self,
        workflow_id: str,
        critique: PolicyCritique | None = None,
        runtime_invariants: RuntimeInvariantReport | None = None,
        handoff_repairs: tuple[HandoffRepairPlan, ...] = (),
    ) -> RecoveryPlaybook:
        critique = critique or self.review_policy(workflow_id)
        runtime_invariants = runtime_invariants or self.runtime_invariant_report(workflow_id)
        playbook = self.contracts.build_recovery_playbook(
            workflow_id=workflow_id,
            findings=critique.findings,
            violations=runtime_invariants.violations,
            handoff_repairs=handoff_repairs,
            pending_outcome_count=len(self.pending_outcomes()),
            pending_approval_count=len(self.pending_approval_requests(workflow_id)),
        )
        self._recovery_playbooks[workflow_id] = playbook
        self._audit_adaptive(
            AuditEventType.RECOVERY_PLAYBOOK,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "step_count": len(playbook.steps),
                "confidence": playbook.confidence,
                "payload": playbook,
            },
        )
        self._persist("recovery_playbooks", playbook)
        return playbook

    def validate_adaptive_evidence_pack(self, pack: AdaptiveEvidencePack) -> EvidencePackValidationResult:
        result = self.contracts.validate_evidence_pack(pack)
        self._evidence_pack_validations.setdefault(pack.workflow_id, []).append(result)
        self._audit_adaptive(
            AuditEventType.EVIDENCE_PACK_VALIDATION,
            pack.workflow_id,
            {
                "workflow_id": pack.workflow_id,
                "schema_version": result.schema_version,
                "valid": result.valid,
                "missing_artifact_count": len(result.missing_artifacts),
                "count_mismatch_count": len(result.count_mismatches),
                "payload": result,
            },
        )
        self._persist("evidence_pack_validations", result)
        return result

    def validate_adaptive_integrity(
        self,
        pack: AdaptiveEvidencePack,
        expected_checksum: str | None = None,
    ) -> AdaptiveIntegrityReport:
        report = self.certifier.integrity_report(pack, expected_checksum=expected_checksum)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_INTEGRITY,
            pack.workflow_id,
            {
                "workflow_id": pack.workflow_id,
                "schema_version": report.schema_version,
                "valid": report.valid,
                "checksum": report.checksum,
                "artifact_count": report.artifact_count,
                "payload": report,
            },
        )
        self._persist("adaptive_integrity", report)
        return report

    def certify_adaptive_readiness(
        self,
        workflow_id: str,
        pack: AdaptiveEvidencePack | None = None,
        expected_checksum: str | None = None,
    ) -> AdaptiveCertificationReport:
        pack = pack or self.build_adaptive_evidence_pack(workflow_id)
        report = self.certifier.certify(pack, expected_checksum=expected_checksum)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_CERTIFICATION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "level": report.level.value,
                "certified": report.certified,
                "violation_count": len(report.violations),
                "evidence_checksum": report.evidence_checksum,
                "payload": report,
            },
        )
        self._persist("adaptive_certifications", report)
        return report

    def authorize_adaptive_action(
        self,
        workflow_id: str,
        action: MaestroAction | str,
        reason: str = "adaptive action authorization",
        *,
        auto_execute: bool = False,
        subject: str | None = None,
        metadata: dict | None = None,
    ) -> ActionAuthorizationReport:
        if isinstance(action, str):
            action = MaestroAction(action)
        profile = self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        tempo = self._tempo_plans.get(workflow_id) or self.plan_tempo(profile, policy, workflow_id=workflow_id)
        contract = self._operating_contracts.get(workflow_id) or self.operating_contract(
            workflow_id, profile=profile, policy=policy, tempo=tempo
        )
        quality_gate = self.quality_gate_report(workflow_id)
        invariants = self.runtime_invariant_report(workflow_id, profile=profile, policy=policy)
        validation = self.validate_operating_contract(
            workflow_id,
            contract=contract,
            quality_gate=quality_gate,
            runtime_invariants=invariants,
            requested_action=action,
            auto_apply_requested=auto_execute,
        )
        requires_approval = action in contract.human_gate_actions
        request_id = None
        authorized = validation.passed and not requires_approval
        if requires_approval:
            request = self.request_human_approval(
                workflow_id,
                action,
                f"{reason}; action requires operating-contract approval",
                policy_version=policy.policy_version,
            )
            request_id = request.request_id
        executed = False
        if auto_execute and authorized:
            self.kernel.intervene(workflow_id, action, subject or workflow_id, reason, metadata or {})
            executed = True
        auth = ActionAuthorizationReport(
            workflow_id=workflow_id,
            action=action,
            authorized=authorized,
            requires_human_approval=requires_approval,
            reason="authorized" if authorized else "blocked by operating contract or human gate",
            contract_validation=validation,
            request_id=request_id,
            violations=validation.violations,
            warnings=validation.warnings,
            executed=executed,
        )
        self._audit_adaptive(
            AuditEventType.ACTION_AUTHORIZATION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "action": action.value,
                "authorized": auth.authorized,
                "requires_human_approval": auth.requires_human_approval,
                "executed": auth.executed,
                "payload": auth,
            },
        )
        self._persist("action_authorizations", auth)
        return auth

    def record_decision(
        self, decision: GovernanceDecision, workflow_id: str | None = None, important: bool = True, **metadata
    ) -> DecisionLedgerEntry:
        return self.ledger.record(decision, workflow_id=workflow_id, important=important, **metadata)

    def pending_outcomes(self, important_only: bool = True) -> tuple[DecisionLedgerEntry, ...]:
        return self.ledger.pending(important_only=important_only)

    def outcome_coverage_ratio(self, important_only: bool = True) -> float:
        return self.ledger.coverage_ratio(important_only=important_only)

    def profile_task(self, workflow: WorkflowPlan | WorkflowRecord) -> TaskProfile:
        profile = self.profiler.profile(workflow)
        workflow_id = workflow.plan.workflow_id if isinstance(workflow, WorkflowRecord) else workflow.workflow_id
        self._profiles[workflow_id] = profile
        return profile

    def select_policy(self, profile: TaskProfile, workflow_id: str | None = None) -> PolicyProfile:
        policy = self.selector.select(profile)
        if workflow_id is not None:
            self._policies[workflow_id] = policy
        return policy

    def plan_tempo(self, profile: TaskProfile, policy: PolicyProfile, workflow_id: str | None = None) -> TempoPlan:
        tempo = self.tempo_controller.plan(profile, policy)
        if workflow_id is not None:
            self._tempo_plans[workflow_id] = tempo
        return tempo

    def apply_policy_profile(self, policy: PolicyProfile) -> None:
        """Explicitly apply a selected policy to the kernel with version tracking."""
        self.kernel.policy = policy.kernel_policy
        self.kernel.governor.policy = policy.kernel_policy

    def suggest_policy_patches(self, critique: PolicyCritique, min_sample_size: int | None = None):
        patches = self.calibrator.suggest_patch(critique, min_sample_size=min_sample_size)
        for patch in patches:
            self._audit_adaptive(
                AuditEventType.POLICY_PATCH,
                critique.workflow_id,
                {
                    "workflow_id": critique.workflow_id,
                    "policy_version": patch.policy_version_from,
                    "patch_field": patch.field,
                    "policy_version_to": patch.policy_version_to,
                    "sample_size": patch.sample_size,
                    "runtime_mode": patch.runtime_mode.value,
                    "payload": patch,
                },
            )
            self._persist(
                "policy_patches",
                PolicyPatchHistoryEntry(
                    patch=patch, status="recommended", workflow_id=critique.workflow_id, reason=patch.reason
                ),
            )
        return patches

    def apply_policy_patch(self, patch, min_sample_size: int | None = None) -> None:
        updated = self.calibrator.apply_patch(self.kernel.policy, patch, min_sample_size=min_sample_size)
        self.kernel.policy = updated
        self.kernel.governor.policy = updated
        self._successful_patch_versions.add(patch.policy_version_to)
        self._audit_adaptive(
            AuditEventType.POLICY_PATCH,
            patch.field,
            {
                "policy_version": patch.policy_version_from,
                "policy_version_to": patch.policy_version_to,
                "patch_field": patch.field,
                "applied": True,
                "runtime_mode": self.calibrator.mode.value,
                "payload": patch,
            },
        )
        self._persist(
            "policy_patches",
            PolicyPatchHistoryEntry(patch=patch, status="applied", reason="controlled adaptive application"),
        )

    def rollback_policy_patch(self, patch) -> None:
        updated = self.calibrator.rollback_patch(self.kernel.policy, patch)
        self.kernel.policy = updated
        self.kernel.governor.policy = updated
        self._successful_patch_versions.discard(patch.policy_version_to)
        self._audit_adaptive(
            AuditEventType.POLICY_ROLLBACK,
            patch.field,
            {
                "policy_version": updated.policy_version,
                "patch_field": patch.field,
                "rolled_back": True,
                "payload": patch,
            },
        )
        self._persist("policy_patches", PolicyPatchHistoryEntry(patch=patch, status="rolled_back", reason="rollback"))

    def policy_patch_history(self) -> tuple[PolicyPatch, ...]:
        return tuple(self.calibrator.patch_history + self.calibrator.applied_patches + self.calibrator.rollback_history)

    def policy_patch_history_entries(self) -> tuple[PolicyPatchHistoryEntry, ...]:
        entries: list[PolicyPatchHistoryEntry] = []
        entries.extend(
            PolicyPatchHistoryEntry(patch=p, status="recommended", reason=p.reason)
            for p in self.calibrator.patch_history
        )
        entries.extend(
            PolicyPatchHistoryEntry(patch=p, status="applied", reason="controlled adaptive application")
            for p in self.calibrator.applied_patches
        )
        entries.extend(
            PolicyPatchHistoryEntry(patch=p, status="rolled_back", reason="rollback")
            for p in self.calibrator.rollback_history
        )
        return tuple(entries)

    def _handle_cycle_patches(
        self,
        workflow_id: str,
        profile: TaskProfile,
        policy: PolicyProfile,
        patches: tuple[PolicyPatch, ...],
        auto_apply_safe_patches: bool,
    ) -> None:
        if not patches or not auto_apply_safe_patches:
            return
        for patch in patches:
            if self.safety_guard.can_auto_apply_patch(profile, policy, patch, self.mode):
                self.apply_policy_patch(patch, min_sample_size=policy.min_sample_size)
            else:
                self.request_human_approval(
                    workflow_id,
                    "policy_patch",
                    "policy patch requires human approval or is not eligible for automatic application",
                    policy_version=patch.policy_version_from,
                    patch_field=patch.field,
                    policy_version_to=patch.policy_version_to,
                    runtime_mode=self.mode.value,
                )

    def checkpoint_schedule_decision(
        self,
        workflow_id: str,
        profile: TaskProfile | None = None,
        policy: PolicyProfile | None = None,
        event: str | None = None,
        milestone: bool = False,
        final: bool = False,
        now: float | None = None,
        coalesce_window_seconds: float = 30.0,
    ) -> CheckpointScheduleDecision:
        profile = profile or self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = policy or self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        last_checkpoint_at = self.checkpoints._last_checkpoint_at.get(workflow_id)
        decision = self.checkpoint_controller.inspect(
            workflow_id,
            profile,
            policy,
            last_checkpoint_at=last_checkpoint_at,
            event=event,
            milestone=milestone,
            final=final,
            now=now,
        )
        previous_coalescing = self._checkpoint_coalescing_decisions.get(workflow_id, ())[-1:]
        previous = previous_coalescing[0].original_decision if previous_coalescing else None
        coalescing = self.efficiency_governor.coalesce_checkpoint_decision(
            decision,
            previous_decision=previous,
            cooldown_seconds=coalesce_window_seconds,
        )
        effective = coalescing.effective_decision
        backpressure = self.efficiency_governor.checkpoint_backpressure_hint(
            effective,
            coalescing,
            now=now,
            max_poll_seconds=max(30.0, coalesce_window_seconds or 30.0),
        )
        self._checkpoint_schedule_decisions.setdefault(workflow_id, []).append(effective)
        self._checkpoint_coalescing_decisions.setdefault(workflow_id, []).append(coalescing)
        self._checkpoint_backpressure_hints.setdefault(workflow_id, []).append(backpressure)
        self._audit_adaptive(
            AuditEventType.CHECKPOINT_SCHEDULE_DECISION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "due": effective.due,
                "trigger": effective.trigger.value if effective.trigger else None,
                "reason": effective.reason,
                "coalesced": coalescing.coalesced,
                "payload": effective,
            },
        )
        self._audit_adaptive(
            AuditEventType.CHECKPOINT_COALESCING_DECISION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "coalesced": coalescing.coalesced,
                "reason": coalescing.reason,
                "cooldown_seconds": coalescing.cooldown_seconds,
                "payload": coalescing,
            },
        )
        self._audit_adaptive(
            AuditEventType.CHECKPOINT_BACKPRESSURE_HINT,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "active": backpressure.active,
                "recommended_delay_seconds": backpressure.recommended_delay_seconds,
                "reason": backpressure.reason,
                "payload": backpressure,
            },
        )
        self._persist("checkpoint_schedule_decisions", effective)
        self._persist("checkpoint_coalescing_decisions", coalescing)
        self._persist("checkpoint_backpressure_hints", backpressure)
        return effective

    def runtime_command_batch_plan(
        self,
        workflow_id: str,
        commands: tuple[RuntimeCommand, ...],
        *,
        max_mutating_commands: int = 1,
        prevent_duplicate: bool = True,
        idempotency_keys: tuple[str | None, ...] = (),
    ) -> RuntimeCommandBatchPlan:
        seen = self._runtime_command_fingerprints.setdefault(workflow_id, set())
        plan = self.efficiency_governor.plan_runtime_command_batch(
            workflow_id,
            commands,
            seen,
            max_mutating_commands=max_mutating_commands,
            prevent_duplicate=prevent_duplicate,
            idempotency_keys=idempotency_keys,
        )
        self._runtime_batch_plans.setdefault(workflow_id, []).append(plan)
        self._audit_adaptive(
            AuditEventType.RUNTIME_COMMAND_BATCH_PLAN,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "input_count": plan.input_count,
                "allowed_count": plan.allowed_count,
                "suppressed_count": plan.suppressed_count,
                "payload": plan,
            },
        )
        self._persist("runtime_command_batch_plans", plan)
        return plan

    def runtime_command_conflict_plan(
        self,
        workflow_id: str,
        commands: tuple[RuntimeCommand, ...],
        *,
        protect_subjects: bool = True,
    ) -> RuntimeCommandConflictPlan:
        """Plan safe suppression of conflicting mutating runtime commands before execution."""
        plan = self.efficiency_governor.plan_runtime_command_conflicts(
            workflow_id,
            commands,
            protect_subjects=protect_subjects,
        )
        self._runtime_conflict_plans.setdefault(workflow_id, []).append(plan)
        self._audit_adaptive(
            AuditEventType.RUNTIME_COMMAND_CONFLICT_PLAN,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "input_count": plan.input_count,
                "conflicting_count": plan.conflicting_count,
                "suppressed_indices": plan.suppressed_indices,
                "primary_action": plan.primary_action.value if plan.primary_action else None,
                "payload": plan,
            },
        )
        self._persist("runtime_command_conflict_plans", plan)
        return plan

    def runtime_command_throttle_plan(
        self,
        workflow_id: str,
        commands: tuple[RuntimeCommand, ...],
        *,
        cooldown_seconds: float = 0.0,
        recent_commands: tuple[object, ...] | None = None,
        now: float | None = None,
    ) -> RuntimeCommandThrottlePlan:
        """Plan conservative throttling for rapid repeated mutating runtime commands.

        The plan is advisory unless callers use it before execution. Escalate/finalize bypass throttling.
        """
        if recent_commands is None:
            recent_commands = tuple(self._runtime_command_results.get(workflow_id, ()))
        plan = self.efficiency_governor.plan_runtime_command_throttle(
            workflow_id,
            commands,
            recent_commands=recent_commands,
            cooldown_seconds=cooldown_seconds,
            now=now,
        )
        self._runtime_throttle_plans.setdefault(workflow_id, []).append(plan)
        self._audit_adaptive(
            AuditEventType.RUNTIME_COMMAND_THROTTLE_PLAN,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "input_count": plan.input_count,
                "suppressed_indices": plan.suppressed_indices,
                "cooldown_seconds": plan.cooldown_seconds,
                "payload": plan,
            },
        )
        self._persist("runtime_command_throttle_plans", plan)
        return plan

    def adaptive_workload_budget_decision(
        self,
        workflow_id: str,
        operation: str,
        *,
        limit: int,
        used_count: int | None = None,
        cost_units: int = 1,
    ) -> AdaptiveWorkloadBudgetDecision:
        """Gate optional adaptive work such as replay, evidence export, or heavy sweeps.

        The decision is advisory and conservative: blocked operations should be deferred, not forced.
        It does not authorize runtime mutation and does not weaken human approval gates.
        """
        existing = self._workload_budget_decisions.get(workflow_id, ())
        if used_count is None:
            used_count = sum(item.cost_units for item in existing if item.operation == str(operation) and item.allowed)
        decision = self.efficiency_governor.workload_budget_decision(
            workflow_id,
            operation,
            used_count=used_count,
            limit=limit,
            cost_units=cost_units,
        )
        self._workload_budget_decisions.setdefault(workflow_id, []).append(decision)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_WORKLOAD_BUDGET_DECISION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "operation": decision.operation,
                "allowed": decision.allowed,
                "used_count": decision.used_count,
                "limit": decision.limit,
                "cost_units": decision.cost_units,
                "reason": decision.reason,
                "payload": decision,
            },
        )
        self._persist("workload_budget_decisions", decision)
        return decision

    def execute_checkpoint_recommendation(
        self,
        report: CheckpointReport,
        *,
        dry_run: bool = True,
        auto_execute: bool = False,
        prevent_duplicate: bool = True,
        idempotency_key: str | None = None,
        throttle_cooldown_seconds: float = 0.0,
    ) -> RuntimeCommandResult:
        command = self.runtime_adapter.build_command(
            workflow_id=report.workflow_id,
            action=report.recommended_action,
            subject=report.workflow_id,
            reason=f"checkpoint recommendation: {report.kind.value}",
            payload={
                "checkpoint_number": report.checkpoint_number,
                "policy_version": report.policy_version,
                "risks": list(report.risks),
                "confidence": report.confidence,
            },
            dry_run=dry_run or not auto_execute,
        )
        authorization = self.authorize_adaptive_action(
            report.workflow_id,
            report.recommended_action,
            reason=command.reason,
            auto_execute=False,
            subject=command.subject,
            metadata=command.payload,
        )
        command = self.runtime_adapter.with_authorization(
            command,
            authorized=authorization.authorized,
            requires_human_approval=authorization.requires_human_approval,
            request_id=authorization.request_id,
        )
        if throttle_cooldown_seconds > 0 and not command.dry_run:
            throttle = self.runtime_command_throttle_plan(
                report.workflow_id,
                (command,),
                cooldown_seconds=throttle_cooldown_seconds,
            )
            if 0 in throttle.suppressed_indices:
                result = RuntimeCommandResult(
                    workflow_id=report.workflow_id,
                    action=command.action,
                    executed=False,
                    dry_run=command.dry_run,
                    authorized=command.authorized,
                    requires_human_approval=command.requires_human_approval,
                    request_id=command.request_id,
                    reason="runtime command suppressed by adaptive throttle",
                    event_payload={"subject": command.subject, "throttle_cooldown_seconds": throttle_cooldown_seconds},
                )
                self._runtime_command_results.setdefault(report.workflow_id, []).append(result)
                self._audit_adaptive(
                    AuditEventType.RUNTIME_COMMAND,
                    report.workflow_id,
                    {
                        "workflow_id": report.workflow_id,
                        "action": result.action.value,
                        "executed": result.executed,
                        "authorized": result.authorized,
                        "requires_human_approval": result.requires_human_approval,
                        "dry_run": result.dry_run,
                        "payload": result,
                    },
                )
                self._persist("runtime_commands", result)
                return result

        seen = self._runtime_command_fingerprints.setdefault(report.workflow_id, set())
        dedupe = self.efficiency_governor.deduplicate_runtime_command(
            command,
            seen,
            idempotency_key=idempotency_key,
            prevent_duplicate=prevent_duplicate,
        )
        self._runtime_deduplication_results.setdefault(report.workflow_id, []).append(dedupe)
        self._audit_adaptive(
            AuditEventType.RUNTIME_COMMAND_DEDUPLICATION,
            report.workflow_id,
            {
                "workflow_id": report.workflow_id,
                "action": dedupe.action.value,
                "duplicate": dedupe.duplicate,
                "suppressed": dedupe.suppressed,
                "reason": dedupe.reason,
                "payload": dedupe,
            },
        )
        self._persist("runtime_command_deduplication", dedupe)
        if dedupe.suppressed:
            result = RuntimeCommandResult(
                workflow_id=command.workflow_id,
                action=command.action,
                executed=False,
                dry_run=command.dry_run,
                authorized=command.authorized,
                requires_human_approval=command.requires_human_approval,
                request_id=command.request_id,
                reason=dedupe.reason,
                event_payload={"command_fingerprint": dedupe.command_fingerprint},
            )
        else:
            result = self.runtime_adapter.execute(self.kernel, command)
            if not command.dry_run and result.executed:
                seen.add(dedupe.command_fingerprint)
        self._runtime_command_results.setdefault(report.workflow_id, []).append(result)
        self._audit_adaptive(
            AuditEventType.RUNTIME_COMMAND,
            report.workflow_id,
            {
                "workflow_id": report.workflow_id,
                "action": result.action.value,
                "executed": result.executed,
                "authorized": result.authorized,
                "requires_human_approval": result.requires_human_approval,
                "dry_run": result.dry_run,
                "payload": result,
            },
        )
        self._persist("runtime_commands", result)
        return result

    def auto_evaluate_pending_outcomes(
        self,
        workflow_id: str,
        *,
        actual_result: str | None = None,
        quality_delta: float | None = None,
        cost_delta: float | None = None,
        latency_delta: float | None = None,
        success_probability_delta: float | None = None,
        max_age_seconds: float = 0.0,
        max_items: int | None = None,
        now: float | None = None,
    ) -> AutoOutcomeReport:
        """Attach conservative outcomes to pending decisions using observable workflow state.

        This is intentionally conservative: if a decision is too fresh and max_age_seconds is positive, it is skipped.
        Callers can still provide explicit outcome metrics when the host runtime has richer signals.
        """
        import time as _time

        now = _time.time() if now is None else now
        workflow = self.kernel.get_workflow(workflow_id)
        pending = [entry for entry in self.pending_outcomes() if entry.workflow_id == workflow_id]
        plan = self.efficiency_governor.plan_outcome_sweep(
            workflow_id,
            len(pending),
            max_batch_size=max_items,
            min_age_seconds=max_age_seconds,
            pending_entries=pending,
            now=now,
        )
        self._outcome_sweep_plans.setdefault(workflow_id, []).append(plan)
        self._audit_adaptive(
            AuditEventType.OUTCOME_SWEEP_PLAN,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "pending_count": plan.pending_count,
                "batch_size": plan.batch_size,
                "remaining_count": plan.remaining_count,
                "reason": plan.reason,
                "payload": plan,
            },
        )
        self._persist("outcome_sweep_plans", plan)
        outcomes = []
        pending_by_id = {entry.decision_id: entry for entry in pending}
        selected_ids = plan.selected_decision_ids or tuple(entry.decision_id for entry in pending[: plan.batch_size])
        for decision_id in selected_ids:
            entry = pending_by_id.get(decision_id)
            if entry is None:
                continue
            inferred_result = actual_result
            if inferred_result is None:
                if workflow.state == WorkflowState.COMPLETED:
                    inferred_result = "success"
                elif workflow.state in {WorkflowState.ESCALATED, WorkflowState.FAILED}:
                    inferred_result = "failed"
                elif workflow.state in {WorkflowState.DEGRADED, WorkflowState.PAUSED}:
                    inferred_result = "partial"
                else:
                    inferred_result = "observed"
            progress = sum(1 for s in workflow.steps.values() if s.state.value == "completed") / max(
                1, len(workflow.steps)
            )
            q_delta = (
                quality_delta
                if quality_delta is not None
                else (0.10 if inferred_result == "success" else (-0.08 if inferred_result == "failed" else 0.0))
            )
            c_delta = cost_delta if cost_delta is not None else 0.0
            l_delta = latency_delta if latency_delta is not None else 0.0
            sp_delta = (
                success_probability_delta
                if success_probability_delta is not None
                else (0.10 * progress if inferred_result in {"success", "observed", "partial"} else -0.10)
            )
            outcome = self.evaluate_outcome(
                entry.decision_id,
                actual_result=inferred_result,
                action=entry.action,
                expected_effect=entry.metadata.get("expected_effect", "improve_workflow"),
                quality_delta=q_delta,
                cost_delta=c_delta,
                latency_delta=l_delta,
                success_probability_delta=sp_delta,
            )
            outcomes.append(outcome)
        skipped = plan.remaining_count
        report = AutoOutcomeReport(
            workflow_id=workflow_id,
            evaluated_count=len(outcomes),
            skipped_count=skipped,
            outcome_coverage_ratio=self.outcome_coverage_ratio(),
            outcomes=tuple(outcomes),
            reason="auto outcome sweep from workflow state",
        )
        self._auto_outcome_reports.setdefault(workflow_id, []).append(report)
        self._audit_adaptive(
            AuditEventType.AUTO_OUTCOME_REPORT,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "evaluated_count": report.evaluated_count,
                "skipped_count": report.skipped_count,
                "outcome_coverage_ratio": report.outcome_coverage_ratio,
                "payload": report,
            },
        )
        self._persist("auto_outcome_reports", report)
        return report

    def maybe_checkpoint(
        self,
        workflow_id: str,
        profile: TaskProfile | None = None,
        policy: PolicyProfile | None = None,
        event: str | None = None,
        milestone: bool = False,
        final: bool = False,
        now: float | None = None,
        coalesce_window_seconds: float = 0.0,
    ) -> CheckpointReport | None:
        profile = profile or self._profiles.get(workflow_id)
        if profile is None:
            profile = self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = policy or self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        if coalesce_window_seconds > 0:
            schedule = self.checkpoint_schedule_decision(
                workflow_id,
                profile=profile,
                policy=policy,
                event=event,
                milestone=milestone,
                final=final,
                now=now,
                coalesce_window_seconds=coalesce_window_seconds,
            )
            if not schedule.due:
                return None
        report = self.checkpoints.maybe_checkpoint(
            self.kernel,
            workflow_id,
            profile,
            policy,
            event=event,
            milestone=milestone,
            final=final,
            now=now,
        )
        if report is not None:
            self._checkpoint_reports.setdefault(workflow_id, []).append(report)
            self._audit_adaptive(
                AuditEventType.ADAPTIVE_CHECKPOINT,
                workflow_id,
                {
                    "workflow_id": workflow_id,
                    "policy_version": report.policy_version,
                    "checkpoint_number": report.checkpoint_number,
                    "kind": report.kind.value,
                    "recommended_action": report.recommended_action.value,
                    "confidence": report.confidence,
                    "payload": report,
                },
            )
            self._analyze_checkpoint(report, profile, policy)
            for event_obj in self.history_recorder.record_checkpoint(report):
                self._record_history_event(event_obj)
            self._persist("checkpoints", report)
        return report

    def _analyze_checkpoint(self, report: CheckpointReport, profile: TaskProfile, policy: PolicyProfile) -> None:
        workflow_id = report.workflow_id
        drift_alerts = self.scan_drift(workflow_id, policy=policy)
        if drift_alerts:
            self._checkpoint_drift_alerts.setdefault(workflow_id, []).extend(drift_alerts)
        handoff_suggestions = self.advise_weak_handoffs(workflow_id, policy=policy)
        if handoff_suggestions:
            self._checkpoint_handoff_suggestions.setdefault(workflow_id, []).extend(handoff_suggestions)
            for suggestion in handoff_suggestions:
                self.plan_handoff_repair(suggestion.edge_id, suggestion=suggestion, profile=profile)
        critique = self.review_policy(workflow_id, policy=policy)
        self._checkpoint_critiques.setdefault(workflow_id, []).append(critique)
        patches = self.suggest_policy_patches(critique, min_sample_size=policy.min_sample_size)
        if patches:
            self._checkpoint_patches.setdefault(workflow_id, []).extend(patches)
        suggestion = self.strategy_bandit.suggest(profile)
        self._audit_adaptive(
            AuditEventType.STRATEGY_SUGGESTION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "strategy": suggestion.strategy.value,
                "confidence": suggestion.confidence,
                "sample_size": suggestion.sample_size,
                "safe_to_apply": suggestion.safe_to_apply,
                "payload": suggestion,
            },
        )

    def scan_drift(self, workflow_id: str, policy: PolicyProfile | None = None) -> tuple[DriftAlert, ...]:
        """Scan workflow, active agents, and active handoff edges for drift at checkpoint time."""
        workflow = self.kernel.get_workflow(workflow_id)
        policy = policy or self._policies.get(workflow_id)
        if policy is not None:
            self.drift_detector.sensitivity = policy.drift_sensitivity
        alerts: list[DriftAlert] = []

        candidates: list[tuple[str, str, str, float]] = [(workflow_id, "workflow", "psi", workflow.psi)]
        assigned_agents = {s.assigned_agent_id for s in workflow.steps.values() if s.assigned_agent_id}
        for agent_id in sorted(assigned_agents):
            record = self.kernel.registry.get(agent_id)
            if record is not None:
                candidates.append((agent_id, "agent", "psi", record.psi))
                candidates.append((agent_id, "agent", "failure_streak_inverse", 1.0 / (1.0 + record.failure_streak)))
        active_agents = assigned_agents
        for edge_id, record in sorted(getattr(self.kernel, "handoffs", {}).items()):
            if record.source_agent_id in active_agents or record.target_agent_id in active_agents:
                candidates.append((edge_id, "handoff", "psi", record.psi))

        for entity_id, entity_type, metric, value in candidates:
            alert = self.drift_detector.observe(entity_id, entity_type, metric, value)
            if alert is not None:
                alerts.append(alert)
                self._audit_adaptive(
                    AuditEventType.DRIFT_ALERT,
                    entity_id,
                    {
                        "workflow_id": workflow_id,
                        "entity_id": entity_id,
                        "entity_type": entity_type,
                        "metric": metric,
                        "severity": alert.severity.value,
                        "payload": alert,
                    },
                )
        return tuple(alerts)

    def advise_weak_handoffs(
        self, workflow_id: str, policy: PolicyProfile | None = None
    ) -> tuple[HandoffSchemaSuggestion, ...]:
        workflow = self.kernel.get_workflow(workflow_id)
        policy = policy or self._policies.get(workflow_id)
        min_edge_psi = policy.kernel_policy.min_edge_psi if policy is not None else self.kernel.policy.min_edge_psi
        active_agents = {s.assigned_agent_id for s in workflow.steps.values() if s.assigned_agent_id}
        suggestions: list[HandoffSchemaSuggestion] = []
        for edge_id, record in sorted(getattr(self.kernel, "handoffs", {}).items()):
            if record.source_agent_id not in active_agents and record.target_agent_id not in active_agents:
                continue
            trend = record.psi - record.previous_psi
            if record.psi < min_edge_psi or trend < -0.05:
                suggestion = self.handoff_advisor.advise(edge_id=edge_id, telemetry=None, edge_psi=record.psi)
                suggestions.append(suggestion)
                self._audit_adaptive(
                    AuditEventType.HANDOFF_SCHEMA_ADVICE,
                    edge_id,
                    {
                        "workflow_id": workflow_id,
                        "edge_id": edge_id,
                        "recommend_mediator": suggestion.recommend_mediator,
                        "confidence": suggestion.confidence,
                        "payload": suggestion,
                    },
                )
        return tuple(suggestions)

    def validate_handoff_payload(self, payload: dict, suggestion: HandoffSchemaSuggestion) -> HandoffValidationResult:
        return self.handoff_advisor.validate_payload(payload, suggestion)

    def plan_handoff_repair(
        self,
        edge_id: str,
        suggestion: HandoffSchemaSuggestion | None = None,
        profile: TaskProfile | None = None,
    ) -> HandoffRepairPlan:
        suggestion = suggestion or self.handoff_advisor.advise(edge_id=edge_id)
        human_review_required = profile is not None and profile.risk.value in {"high", "critical"}
        steps = (
            "freeze the current handoff artifact as audit evidence",
            "validate payload against the suggested handoff schema",
            "ask upstream agent to fill missing required fields",
            "route through Synthesizer/Mediator if validation remains weak",
            "record the repaired handoff and compare edge psi at the next checkpoint",
        )
        plan = HandoffRepairPlan(
            edge_id=edge_id,
            suggestion=suggestion,
            steps=steps,
            validation_required=True,
            mediator_agent_role="Synthesizer" if suggestion.recommend_mediator else None,
            human_review_required=human_review_required,
            confidence=suggestion.confidence,
        )
        self._audit_adaptive(
            AuditEventType.HANDOFF_REPAIR_PLAN,
            edge_id,
            {
                "edge_id": edge_id,
                "mediator_agent_role": plan.mediator_agent_role,
                "human_review_required": plan.human_review_required,
                "confidence": plan.confidence,
                "payload": plan,
            },
        )
        self._persist("handoff_repair_plans", plan)
        return plan

    def evaluate_outcome(
        self,
        decision_id: str,
        actual_result: str,
        decision: GovernanceDecision | None = None,
        action: str | None = None,
        expected_effect: str = "improve_workflow",
        **metrics,
    ) -> DecisionOutcome:
        resolved_action = action or (decision.new_state.value if decision is not None else "unknown")
        outcome = self.evaluator.evaluate(
            decision_id=decision_id,
            action=resolved_action,
            expected_effect=expected_effect,
            actual_result=actual_result,
            **metrics,
        )
        entry = self.ledger.attach_outcome(outcome)
        workflow_id = entry.workflow_id if entry is not None else None
        profile = self._profiles.get(workflow_id) if workflow_id is not None else None
        if action:
            try:
                self.strategy_bandit.record(MaestroAction(action), outcome.decision_quality, profile=profile)
            except ValueError:
                pass
        if workflow_id is not None:
            history_event = self.history_recorder.record_outcome(
                workflow_id, outcome, policy=self._policies.get(workflow_id)
            )
            self._record_history_event(history_event)
        self._persist("decision_outcomes", outcome)
        self._audit_adaptive(
            AuditEventType.DECISION_OUTCOME,
            decision_id,
            {
                "decision_id": decision_id,
                "policy_version": getattr(decision, "policy_version", "unversioned")
                if decision is not None
                else "unversioned",
                "decision_quality": outcome.decision_quality,
                "actual_result": outcome.actual_result,
                "payload": outcome,
            },
        )
        return outcome

    def review_policy(self, workflow_id: str, policy: PolicyProfile | None = None) -> PolicyCritique:
        profile = self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = policy or self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        outcomes = tuple(self.evaluator.outcomes.values())
        checkpoints = tuple(self._checkpoint_reports.get(workflow_id, ()))
        critique = self.critic.review(self.kernel, workflow_id, policy, checkpoints=checkpoints, outcomes=outcomes)
        self._audit_adaptive(
            AuditEventType.POLICY_CRITIQUE,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "policy_version": critique.policy_version,
                "confidence": critique.confidence,
                "finding_count": len(critique.findings),
                "suggested_patch_count": len(critique.suggested_changes),
                "payload": critique,
            },
        )
        return critique

    def enforce_budget_guard(
        self, workflow_id: str, cost_usage_ratio: float, profile: TaskProfile, tempo: TempoPlan
    ) -> MaestroAction | None:
        if cost_usage_ratio < tempo.budget_stop_threshold:
            return None
        action = MaestroAction.ESCALATE if profile.risk.value in {"high", "critical"} else MaestroAction.PAUSE
        self.kernel.intervene(
            workflow_id,
            action,
            workflow_id,
            f"budget usage {cost_usage_ratio:.2f} exceeded threshold {tempo.budget_stop_threshold:.2f}",
            {"cost_usage_ratio": cost_usage_ratio, "budget_stop_threshold": tempo.budget_stop_threshold},
        )
        self._audit_adaptive(
            AuditEventType.BUDGET_GUARD,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "action": action.value,
                "cost_usage_ratio": cost_usage_ratio,
                "budget_stop_threshold": tempo.budget_stop_threshold,
            },
        )
        return action

    def run_adaptive_cycle(
        self,
        workflow_id: str,
        telemetry: WorkflowTelemetry | None = None,
        event: str | None = None,
        milestone: bool = False,
        final: bool = False,
        now: float | None = None,
        cost_usage_ratio: float | None = None,
        apply_selected_policy: bool = True,
        auto_apply_safe_patches: bool = False,
    ) -> AdaptiveCycleReport:
        """Run one safe adaptive governance cycle around an existing workflow."""
        workflow = self.kernel.get_workflow(workflow_id)
        profile = self._profiles.get(workflow_id) or self.profile_task(workflow)
        policy = self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        if apply_selected_policy:
            self.apply_policy_profile(policy)
        tempo = self.plan_tempo(profile, policy, workflow_id=workflow_id)
        contract = self.operating_contract(workflow_id, profile=profile, policy=policy, tempo=tempo)

        budget_action = None
        if cost_usage_ratio is not None:
            budget_action = self.enforce_budget_guard(workflow_id, cost_usage_ratio, profile, tempo)

        decision_id = None
        if telemetry is not None:
            decision = self.kernel.observe_workflow(workflow_id, telemetry)
            decision_id = decision.decision_id
            self.ledger.record(decision, workflow_id=workflow_id, important=True, source="adaptive_cycle")

        checkpoint = self.maybe_checkpoint(
            workflow_id,
            profile=profile,
            policy=policy,
            event=event,
            milestone=milestone,
            final=final,
            now=now,
        )

        drift_alerts = tuple(self._checkpoint_drift_alerts.get(workflow_id, ()))
        handoff_suggestions = tuple(self._checkpoint_handoff_suggestions.get(workflow_id, ()))
        critique = self._checkpoint_critiques.get(workflow_id, [None])[-1]
        patches = tuple(self._checkpoint_patches.get(workflow_id, ()))
        self._handle_cycle_patches(workflow_id, profile, policy, patches, auto_apply_safe_patches)
        strategy = self.strategy_bandit.suggest(profile)
        invariants = self.runtime_invariant_report(
            workflow_id,
            profile=profile,
            policy=policy,
            auto_apply_requested=auto_apply_safe_patches,
        )
        quality_gate = self.quality_gate_report(workflow_id)
        contract_validation = self.validate_operating_contract(
            workflow_id,
            contract=contract,
            quality_gate=quality_gate,
            runtime_invariants=invariants,
            requested_action=budget_action,
            auto_apply_requested=auto_apply_safe_patches,
        )
        report = AdaptiveCycleReport(
            workflow_id=workflow_id,
            profile=profile,
            policy=policy,
            tempo=tempo,
            decision_id=decision_id,
            checkpoint=checkpoint,
            drift_alerts=drift_alerts,
            handoff_suggestions=handoff_suggestions,
            policy_critique=critique,
            policy_patches=patches,
            strategy_suggestion=strategy,
            budget_action=budget_action,
            runtime_invariants=invariants,
            quality_gate=quality_gate,
            operating_contract=contract,
            contract_validation=contract_validation,
            outcome_coverage_ratio=self.outcome_coverage_ratio(),
        )
        convergence = self.convergence_monitor.observe(report)
        report = replace(report, convergence_report=convergence)
        self._convergence_reports.setdefault(workflow_id, []).append(convergence)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_CONVERGENCE,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "stable": convergence.stable,
                "window_size": convergence.window_size,
                "recommendation": convergence.recommendation,
                "payload": convergence,
            },
        )
        self._persist("adaptive_convergence", convergence)
        self._cycle_reports.append(report)
        history_event = self.history_recorder.record_cycle(report)
        self._record_history_event(history_event)
        self._persist("adaptive_cycles", report)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_CYCLE,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "policy_version": policy.policy_version,
                "decision_id": decision_id,
                "checkpoint_created": checkpoint is not None,
                "drift_alert_count": len(drift_alerts),
                "handoff_suggestion_count": len(handoff_suggestions),
                "patch_count": len(patches),
                "budget_action": budget_action.value if budget_action else None,
                "runtime_invariants_passed": invariants.passed,
                "quality_gate_passed": quality_gate.passed,
                "contract_passed": contract_validation.passed,
                "convergence_stable": convergence.stable,
                "payload": report,
            },
        )
        return report

    def pulse_adaptive(self, workflow_id: str, **kwargs) -> AdaptiveCycleReport:
        """Alias matching the paper's pulse-style interface."""
        return self.run_adaptive_cycle(workflow_id, **kwargs)

    def metrics_snapshot(self) -> MetricsSnapshot:
        checkpoints = [report for reports in self._checkpoint_reports.values() for report in reports]
        snapshot = self.metrics_collector.snapshot(
            self.kernel,
            outcomes=self.evaluator.outcomes.values(),
            checkpoints=checkpoints,
            ledger=self.ledger,
            applied_patches=self.calibrator.applied_patches,
            successful_patch_versions=self._successful_patch_versions,
        )
        self._audit_adaptive(
            AuditEventType.METRICS_SNAPSHOT,
            "adaptive_metrics",
            {"payload": snapshot},
        )
        self._persist("metrics_snapshots", snapshot)
        return snapshot

    def quality_gate_report(
        self, workflow_id: str, metrics: MetricsSnapshot | None = None
    ) -> AdaptiveQualityGateReport:
        profile = self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        metrics = metrics or self.metrics_snapshot()
        report = self.quality_gates.evaluate(
            workflow_id=workflow_id,
            metrics=metrics,
            runtime_mode=self.mode,
            pending_outcome_count=len(self.pending_outcomes()),
            pending_approval_count=len(self.pending_approval_requests(workflow_id)),
            critical=profile.risk.value == "critical",
        )
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_QUALITY_GATE,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "passed": report.passed,
                "eligible_next_mode": report.eligible_next_mode.value if report.eligible_next_mode else None,
                "violation_count": len(report.violations),
                "warning_count": len(report.warnings),
                "payload": report,
            },
        )
        self._persist("quality_gates", report)
        return report

    def propose_runtime_mode_transition(
        self,
        workflow_id: str,
        requested_mode: RuntimeMode | str | None = None,
    ) -> AdaptiveModeTransitionDecision:
        """Evaluate whether the toolkit can safely move to another runtime mode.

        This is evidence-based and read-only. Critical and high-risk workflows remain human-gated.
        """
        if isinstance(requested_mode, str):
            requested_mode = RuntimeMode(requested_mode)
        metrics = self.metrics_snapshot()
        quality_gate = self.quality_gate_report(workflow_id, metrics=metrics)
        profile = self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        invariants = self.runtime_invariant_report(workflow_id, profile=profile, policy=policy)
        target = requested_mode or quality_gate.eligible_next_mode or self.mode
        decision = self.operations_governor.decide_mode_transition(
            workflow_id=workflow_id,
            current_mode=self.mode,
            requested_mode=target,
            profile=profile,
            quality_gate=quality_gate,
            runtime_invariants=invariants,
            metrics=metrics,
            pending_outcome_count=len(self.pending_outcomes()),
            pending_approval_count=len(self.pending_approval_requests(workflow_id)),
        )
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_MODE_TRANSITION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "current_mode": decision.current_mode.value,
                "requested_mode": decision.requested_mode.value,
                "allowed": decision.allowed,
                "required_human_approval": decision.required_human_approval,
                "violation_count": len(decision.violations),
                "payload": decision,
            },
        )
        self._persist("mode_transitions", decision)
        return decision

    def apply_runtime_mode_transition(self, decision: AdaptiveModeTransitionDecision) -> RuntimeMode:
        """Apply an already evaluated runtime-mode transition only when safety evidence allows it."""
        if not decision.allowed:
            if decision.required_human_approval:
                self.request_human_approval(
                    decision.workflow_id,
                    "runtime_mode_transition",
                    decision.reason,
                    requested_mode=decision.requested_mode.value,
                    current_mode=decision.current_mode.value,
                )
            raise RuntimeError(decision.reason)
        self.mode = decision.requested_mode
        self.calibrator.mode = decision.requested_mode
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_MODE_TRANSITION,
            decision.workflow_id,
            {
                "workflow_id": decision.workflow_id,
                "current_mode": decision.current_mode.value,
                "requested_mode": decision.requested_mode.value,
                "applied": True,
                "payload": decision,
            },
        )
        return self.mode

    def verify_applied_patches(
        self,
        workflow_id: str,
        rollback_on_regression: bool = False,
        min_decision_quality: float = 0.55,
    ) -> tuple[PatchVerificationResult, ...]:
        """Verify applied policy patches against recent outcomes and optionally roll back regressions."""
        outcomes = list(self.evaluator.outcomes.values())
        recent_quality = outcomes[-1].decision_quality if outcomes else None
        metrics = self.metrics_snapshot()
        results = self.operations_governor.verify_patches(
            workflow_id=workflow_id,
            patches=self.calibrator.applied_patches,
            metrics=metrics,
            recent_decision_quality=recent_quality,
            min_decision_quality=min_decision_quality,
        )
        for result in results:
            self._audit_adaptive(
                AuditEventType.PATCH_VERIFICATION,
                workflow_id,
                {
                    "workflow_id": workflow_id,
                    "patch_field": result.patch.field,
                    "policy_version_to": result.patch.policy_version_to,
                    "status": result.status,
                    "rollback_recommended": result.rollback_recommended,
                    "confidence": result.confidence,
                    "payload": result,
                },
            )
            self._persist("patch_verifications", result)
            if rollback_on_regression and result.rollback_recommended:
                self.rollback_policy_patch(result.patch)
        return results

    def adaptive_evidence_digest(
        self,
        workflow_id: str,
        pack: AdaptiveEvidencePack | None = None,
        *,
        omit_artifacts: tuple[str, ...] = (),
    ) -> AdaptiveEvidenceDigest:
        """Create a lightweight checksum manifest for an evidence pack without deleting source evidence."""
        pack = pack or self.build_adaptive_evidence_pack(workflow_id)
        digest = self.efficiency_governor.evidence_pack_digest(pack, omit_artifacts=omit_artifacts)
        self._evidence_digests.setdefault(workflow_id, []).append(digest)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_EVIDENCE_DIGEST,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "source_schema_version": digest.source_schema_version,
                "digest_schema_version": digest.digest_schema_version,
                "artifact_count": digest.artifact_count,
                "stable_checksum": digest.stable_checksum,
                "payload": digest,
            },
        )
        self._persist("adaptive_evidence_digests", digest)
        return digest

    def adaptive_evidence_delta(
        self,
        workflow_id: str,
        previous: AdaptiveEvidenceDigest,
        current: AdaptiveEvidenceDigest,
    ) -> AdaptiveEvidenceDelta:
        """Compare two evidence digests and record a low-cost review delta."""
        delta = self.efficiency_governor.evidence_delta_digest(previous, current)
        self._evidence_deltas.setdefault(workflow_id, []).append(delta)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_EVIDENCE_DELTA,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "changed_count": delta.changed_count,
                "unchanged_count": delta.unchanged_count,
                "schema_version": delta.schema_version,
                "payload": delta,
            },
        )
        self._persist("adaptive_evidence_deltas", delta)
        return delta

    def generate_report_encryption_key(self) -> str:
        """Generate a URL-safe base64 256-bit key for AES-256-GCM report encryption.

        The returned key is a secret. The toolkit never stores it in reports, evidence packs, or audit logs.
        """
        return self.report_encryptor.generate_key_b64()

    def encrypt_adaptive_report(
        self,
        workflow_id: str,
        report,
        key: bytes | str,
        *,
        report_kind: str = "adaptive_report",
        key_id: str = "default",
        path: str | Path | None = None,
    ) -> EncryptedAdaptiveReport:
        """Encrypt an adaptive report/evidence artifact with AES-256-GCM.

        Encryption is outside the core kernel and is activated only when the caller supplies a 256-bit key.
        Raw key material is never persisted. The encrypted envelope stores nonce, AAD, ciphertext, and hashes only.
        """
        encrypted = self.report_encryptor.encrypt_report(
            workflow_id=workflow_id,
            report=report,
            key=key,
            report_kind=report_kind,
            key_id=key_id,
        )
        self._encrypted_reports.setdefault(workflow_id, []).append(encrypted)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_REPORT_ENCRYPTION,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "report_kind": encrypted.report_kind,
                "algorithm": encrypted.algorithm,
                "key_id": encrypted.key_id,
                "ciphertext_sha256": encrypted.ciphertext_sha256,
                "plaintext_sha256": encrypted.plaintext_sha256,
                "payload": encrypted,
            },
        )
        self._persist("encrypted_reports", encrypted)
        if path is not None:
            self.report_encryptor.write_encrypted_report(encrypted, path)
        return encrypted

    def decrypt_adaptive_report(
        self,
        encrypted: EncryptedAdaptiveReport,
        key: bytes | str,
    ) -> AdaptiveReportDecryptionResult:
        """Decrypt an AES-256-GCM adaptive report envelope and verify authentication/hash metadata."""
        result = self.report_encryptor.decrypt_report(encrypted, key)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_REPORT_DECRYPTION,
            encrypted.workflow_id,
            {
                "workflow_id": encrypted.workflow_id,
                "report_kind": encrypted.report_kind,
                "valid": result.valid,
                "reason": result.reason,
                "plaintext_sha256": result.plaintext_sha256,
                "ciphertext_sha256": result.ciphertext_sha256,
            },
        )
        if self.store is not None:
            self.store.append(
                "adaptive_report_decryptions",
                {
                    "workflow_id": encrypted.workflow_id,
                    "report_kind": encrypted.report_kind,
                    "valid": result.valid,
                    "reason": result.reason,
                    "plaintext_sha256": result.plaintext_sha256,
                    "ciphertext_sha256": result.ciphertext_sha256,
                    "schema_version": result.schema_version,
                    "created_at": result.created_at,
                },
            )
        return result

    def build_encrypted_adaptive_evidence_pack(
        self,
        workflow_id: str,
        key: bytes | str,
        *,
        key_id: str = "default",
        path: str | Path | None = None,
    ) -> EncryptedAdaptiveReport:
        """Build the current evidence pack and encrypt it as an AES-256-GCM report envelope."""
        pack = self.build_adaptive_evidence_pack(workflow_id)
        return self.encrypt_adaptive_report(
            workflow_id=workflow_id,
            report=pack,
            key=key,
            report_kind="adaptive_evidence_pack",
            key_id=key_id,
            path=path,
        )

    def adaptive_encrypted_report_index(
        self,
        workflow_id: str,
        encrypted_reports: tuple[EncryptedAdaptiveReport, ...] | None = None,
    ) -> AdaptiveEncryptedReportIndex:
        """Index encrypted reports for lightweight review without decryption or key exposure."""
        reports = (
            encrypted_reports if encrypted_reports is not None else tuple(self._encrypted_reports.get(workflow_id, ()))
        )
        index = self.efficiency_governor.encrypted_report_index(workflow_id, reports)
        self._encrypted_report_indexes.setdefault(workflow_id, []).append(index)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_ENCRYPTED_REPORT_INDEX,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "encrypted_count": index.encrypted_count,
                "schema_version": index.schema_version,
                "payload": index,
            },
        )
        self._persist("encrypted_report_indexes", index)
        return index

    def adaptive_ui_snapshot(
        self,
        workflow_id: str,
        pack: AdaptiveEvidencePack | None = None,
        *,
        digest: AdaptiveEvidenceDigest | None = None,
        encrypted_index: AdaptiveEncryptedReportIndex | None = None,
        max_recommendations: int = 6,
    ) -> AdaptiveUiSnapshot:
        """Create a compact, UI-safe snapshot for offline HTML review."""
        pack = pack or self.build_adaptive_evidence_pack(workflow_id)
        digest = digest or self.adaptive_evidence_digest(workflow_id, pack)
        encrypted_index = encrypted_index or self.adaptive_encrypted_report_index(workflow_id)
        snapshot = self.efficiency_governor.ui_snapshot_from_evidence_pack(
            pack,
            digest=digest,
            encrypted_index=encrypted_index,
            max_recommendations=max_recommendations,
        )
        self._ui_snapshots.setdefault(workflow_id, []).append(snapshot)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_UI_SNAPSHOT,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "status": snapshot.status,
                "schema_version": snapshot.schema_version,
                "encrypted_report_count": snapshot.encrypted_report_count,
                "payload": snapshot,
            },
        )
        self._persist("ui_snapshots", snapshot)
        return snapshot

    def write_adaptive_dashboard_html(
        self,
        workflow_id: str,
        path: str | Path,
        snapshot: AdaptiveUiSnapshot | None = None,
    ) -> Path:
        """Write a standalone HTML dashboard with an embedded UI-safe snapshot."""
        snapshot = snapshot or self.adaptive_ui_snapshot(workflow_id)
        return write_adaptive_dashboard_html(snapshot, path)

    def build_adaptive_dashboard_html(
        self,
        workflow_id: str,
        snapshot: AdaptiveUiSnapshot | None = None,
    ) -> str:
        """Return standalone HTML for review without writing to disk."""
        snapshot = snapshot or self.adaptive_ui_snapshot(workflow_id)
        return build_adaptive_dashboard_html(snapshot)

    def adaptive_efficiency_report(self, workflow_id: str) -> AdaptiveEfficiencyReport:
        """Summarize duplicate-work reductions for a workflow without mutating kernel state."""
        report = self.efficiency_governor.efficiency_report(
            workflow_id=workflow_id,
            checkpoint_coalescing=self._checkpoint_coalescing_decisions.get(workflow_id, ()),
            runtime_deduplication=self._runtime_deduplication_results.get(workflow_id, ()),
            runtime_results=self._runtime_command_results.get(workflow_id, ()),
            auto_outcomes=self._auto_outcome_reports.get(workflow_id, ()),
            checkpoint_backpressure=self._checkpoint_backpressure_hints.get(workflow_id, ()),
            runtime_batches=self._runtime_batch_plans.get(workflow_id, ()),
            outcome_sweep_plans=self._outcome_sweep_plans.get(workflow_id, ()),
            workload_budgets=self._workload_budget_decisions.get(workflow_id, ()),
            runtime_conflicts=self._runtime_conflict_plans.get(workflow_id, ()),
            evidence_digests=self._evidence_digests.get(workflow_id, ()),
            runtime_throttles=self._runtime_throttle_plans.get(workflow_id, ()),
            evidence_deltas=self._evidence_deltas.get(workflow_id, ()),
            encrypted_reports=self._encrypted_reports.get(workflow_id, ()),
            encrypted_report_indexes=self._encrypted_report_indexes.get(workflow_id, ()),
            ui_snapshots=self._ui_snapshots.get(workflow_id, ()),
        )
        self._efficiency_reports.setdefault(workflow_id, []).append(report)
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_EFFICIENCY_REPORT,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "checkpoint_coalesced_count": report.checkpoint_coalesced_count,
                "duplicate_runtime_command_count": report.duplicate_runtime_command_count,
                "runtime_command_count": report.runtime_command_count,
                "checkpoint_backpressure_count": report.checkpoint_backpressure_count,
                "runtime_batch_suppressed_count": report.runtime_batch_suppressed_count,
                "outcome_sweep_planned_count": report.outcome_sweep_planned_count,
                "outcome_sweep_deferred_count": report.outcome_sweep_deferred_count,
                "workload_budget_blocked_count": report.workload_budget_blocked_count,
                "runtime_conflict_suppressed_count": report.runtime_conflict_suppressed_count,
                "evidence_digest_count": report.evidence_digest_count,
                "runtime_throttle_suppressed_count": report.runtime_throttle_suppressed_count,
                "evidence_delta_count": report.evidence_delta_count,
                "encrypted_report_count": report.encrypted_report_count,
                "encrypted_report_index_count": report.encrypted_report_index_count,
                "ui_snapshot_count": report.ui_snapshot_count,
                "payload": report,
            },
        )
        self._persist("adaptive_efficiency_reports", report)
        return report

    def build_adaptive_evidence_pack(
        self,
        workflow_id: str,
        path: str | Path | None = None,
        transition_decision: AdaptiveModeTransitionDecision | None = None,
    ) -> AdaptiveEvidencePack:
        """Export the complete adaptive evidence envelope for review or handoff."""
        profile = self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        policy = self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        tempo = self._tempo_plans.get(workflow_id) or self.plan_tempo(profile, policy, workflow_id=workflow_id)
        metrics = self.metrics_snapshot()
        quality_gate = self.quality_gate_report(workflow_id, metrics=metrics)
        invariants = self.runtime_invariant_report(workflow_id, profile=profile, policy=policy)
        contract = self._operating_contracts.get(workflow_id) or self.operating_contract(
            workflow_id, profile=profile, policy=policy, tempo=tempo
        )
        contract_validation = self._contract_validations.get(workflow_id, [None])[-1]
        if contract_validation is None:
            contract_validation = self.validate_operating_contract(
                workflow_id,
                contract=contract,
                quality_gate=quality_gate,
                runtime_invariants=invariants,
            )
        convergence = self._convergence_reports.get(workflow_id, [None])[-1]
        recovery_playbook = self._recovery_playbooks.get(workflow_id)
        pack = self.operations_governor.build_evidence_pack(
            workflow_id=workflow_id,
            profile=profile,
            policy=policy,
            tempo=tempo,
            metrics=metrics,
            quality_gate=quality_gate,
            runtime_invariants=invariants,
            checkpoints=self._checkpoint_reports.get(workflow_id, ()),
            drift_alerts=self._checkpoint_drift_alerts.get(workflow_id, ()),
            handoff_suggestions=self._checkpoint_handoff_suggestions.get(workflow_id, ()),
            policy_critiques=self._checkpoint_critiques.get(workflow_id, ()),
            policy_patches=self._checkpoint_patches.get(workflow_id, ()),
            approvals=self.pending_approval_requests(workflow_id),
            history=self.workflow_history(workflow_id),
            replay_results=(),
            transition_decision=transition_decision,
            operating_contract=contract,
            contract_validation=contract_validation,
            convergence_report=convergence,
            recovery_playbook=recovery_playbook,
            runtime_commands=self._runtime_command_results.get(workflow_id, ()),
            auto_outcome_reports=self._auto_outcome_reports.get(workflow_id, ()),
            checkpoint_coalescing=self._checkpoint_coalescing_decisions.get(workflow_id, ()),
            runtime_deduplication=self._runtime_deduplication_results.get(workflow_id, ()),
            efficiency_reports=self._efficiency_reports.get(workflow_id, ()),
            checkpoint_backpressure=self._checkpoint_backpressure_hints.get(workflow_id, ()),
            runtime_batches=self._runtime_batch_plans.get(workflow_id, ()),
            outcome_sweep_plans=self._outcome_sweep_plans.get(workflow_id, ()),
            workload_budget_decisions=self._workload_budget_decisions.get(workflow_id, ()),
            runtime_conflicts=self._runtime_conflict_plans.get(workflow_id, ()),
            evidence_digests=self._evidence_digests.get(workflow_id, ()),
            runtime_throttles=self._runtime_throttle_plans.get(workflow_id, ()),
            evidence_deltas=self._evidence_deltas.get(workflow_id, ()),
            encrypted_reports=self._encrypted_reports.get(workflow_id, ()),
            encrypted_report_indexes=self._encrypted_report_indexes.get(workflow_id, ()),
            ui_snapshots=self._ui_snapshots.get(workflow_id, ()),
        )
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_EVIDENCE_PACK,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "schema_version": pack.schema_version,
                "counts": pack.counts,
                "payload": pack,
            },
        )
        self._persist("evidence_packs", pack)
        self.validate_adaptive_evidence_pack(pack)
        if path is not None:
            self.operations_governor.write_evidence_pack(pack, path)
        elif self.store is not None:
            self.store.save_snapshot(f"evidence_pack_{workflow_id}", pack)
        return pack

    def replay_history(
        self,
        workflow_id: str,
        baseline: PolicyProfile,
        candidate: PolicyProfile,
        history: tuple[WorkflowHistoryEvent, ...],
    ) -> ReplayComparison:
        comparison = self.replay_lab.replay_history(workflow_id, baseline, candidate, history)
        self._audit_adaptive(
            AuditEventType.REPLAY_COMPARISON,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "baseline_policy": comparison.baseline_policy.value,
                "candidate_policy": comparison.candidate_policy.value,
                "recommendation": comparison.recommendation,
                "confidence": comparison.confidence,
                "payload": comparison,
            },
        )
        self._persist("replay_comparisons", comparison)
        return comparison

    def replay_counterfactuals(
        self,
        workflow_id: str,
        baseline: PolicyProfile | None = None,
        candidate_policies: tuple[PolicyProfile, ...] = (),
    ) -> tuple[CounterfactualReplayResult, ...]:
        profile = self._profiles.get(workflow_id) or self.profile_task(self.kernel.get_workflow(workflow_id))
        baseline = baseline or self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        results = self.replay_lab.counterfactual_scenarios(
            workflow_id,
            baseline=baseline,
            history=self.workflow_history(workflow_id),
            candidate_policies=candidate_policies,
        )
        for result in results:
            self._audit_adaptive(
                AuditEventType.REPLAY_SCENARIO,
                workflow_id,
                {
                    "workflow_id": workflow_id,
                    "scenario": result.scenario,
                    "recommendation": result.recommendation,
                    "confidence": result.confidence,
                    "payload": result,
                },
            )
            self._persist("replay_scenarios", result)
        return results

    def workflow_history(self, workflow_id: str) -> tuple[WorkflowHistoryEvent, ...]:
        return self.history_recorder.history(workflow_id)

    def finalize_adaptive_review(
        self,
        workflow_id: str,
        candidate_policies: tuple[PolicyProfile, ...] = (),
        now: float | None = None,
    ) -> AdaptiveReviewReport:
        """Produce the paper's final review: final checkpoint, critique, metrics, replay, and safe recommendations."""
        workflow = self.kernel.get_workflow(workflow_id)
        profile = self._profiles.get(workflow_id) or self.profile_task(workflow)
        policy = self._policies.get(workflow_id) or self.select_policy(profile, workflow_id=workflow_id)
        final_checkpoint = self.maybe_checkpoint(workflow_id, profile=profile, policy=policy, final=True, now=now)
        final_critique = self.review_policy(workflow_id, policy=policy)
        history = self.workflow_history(workflow_id)
        replay_comparisons = tuple(
            self.replay_history(workflow_id, baseline=policy, candidate=candidate, history=history)
            for candidate in candidate_policies
            if candidate.name != policy.name
        )
        counterfactual_results = self.replay_counterfactuals(
            workflow_id, baseline=policy, candidate_policies=candidate_policies
        )
        metrics = self.metrics_snapshot()
        quality_gate = self.quality_gate_report(workflow_id, metrics=metrics)
        invariants = self.runtime_invariant_report(workflow_id, profile=profile, policy=policy)
        tempo = self._tempo_plans.get(workflow_id) or self.plan_tempo(profile, policy, workflow_id=workflow_id)
        contract = self._operating_contracts.get(workflow_id) or self.operating_contract(
            workflow_id, profile=profile, policy=policy, tempo=tempo
        )
        contract_validation = self.validate_operating_contract(
            workflow_id,
            contract=contract,
            quality_gate=quality_gate,
            runtime_invariants=invariants,
        )
        convergence = self.convergence_report(workflow_id)
        handoff_repairs = tuple(
            self.plan_handoff_repair(s.edge_id, suggestion=s, profile=profile)
            for s in self._checkpoint_handoff_suggestions.get(workflow_id, ())
        )
        recovery_playbook = self.build_recovery_playbook(
            workflow_id,
            critique=final_critique,
            runtime_invariants=invariants,
            handoff_repairs=handoff_repairs,
        )
        pending_outcome_count = len(self.pending_outcomes())
        approval_request_count = len(self.pending_approval_requests(workflow_id))
        recommendations: list[str] = list(final_critique.findings)
        if pending_outcome_count:
            recommendations.append("attach outcomes to all important decisions before enabling wider adaptation")
        if metrics.outcome_coverage_ratio < 0.95:
            recommendations.append("raise decision outcome coverage before trusting policy calibration")
        for comparison in replay_comparisons:
            if comparison.recommendation == "prefer_candidate":
                recommendations.append(
                    f"consider {comparison.candidate_policy.value} for similar workflows after review"
                )
        if approval_request_count:
            recommendations.append("resolve pending human approval requests before applying restricted changes")
        if not quality_gate.passed:
            recommendations.extend(f"quality gate violation: {v}" for v in quality_gate.violations)
        if not invariants.passed:
            recommendations.extend(f"runtime invariant violation: {v}" for v in invariants.violations)
        if not contract_validation.passed:
            recommendations.extend(f"operating contract violation: {v}" for v in contract_validation.violations)
        if not convergence.stable:
            recommendations.append(f"hold adaptive expansion: {convergence.recommendation}")
        if recovery_playbook.steps:
            recommendations.append(
                "execute or explicitly defer the generated recovery playbook before wider adaptation"
            )
        for result in counterfactual_results:
            if result.recommendation == "prefer_scenario":
                recommendations.append(f"review counterfactual scenario: {result.scenario}")

        evidence_pack = self.build_adaptive_evidence_pack(workflow_id)
        integrity_report = self.validate_adaptive_integrity(evidence_pack)
        certification_report = self.certify_adaptive_readiness(workflow_id, pack=evidence_pack)
        if not certification_report.certified:
            recommendations.append(f"adaptive certification blocked: {certification_report.reason}")

        report = AdaptiveReviewReport(
            workflow_id=workflow_id,
            final_checkpoint=final_checkpoint,
            final_critique=final_critique,
            metrics=metrics,
            quality_gate=quality_gate,
            runtime_invariants=invariants,
            operating_contract=contract,
            contract_validation=contract_validation,
            convergence_report=convergence,
            recovery_playbook=recovery_playbook,
            replay_comparisons=replay_comparisons,
            counterfactual_results=counterfactual_results,
            pending_outcome_count=pending_outcome_count,
            patch_history_count=len(self.policy_patch_history()),
            approval_request_count=approval_request_count,
            recommendations=tuple(dict.fromkeys(recommendations)),
            integrity_report=integrity_report,
            certification_report=certification_report,
        )
        self._audit_adaptive(
            AuditEventType.ADAPTIVE_REVIEW,
            workflow_id,
            {
                "workflow_id": workflow_id,
                "policy_version": policy.policy_version,
                "recommendation_count": len(report.recommendations),
                "pending_outcome_count": pending_outcome_count,
                "approval_request_count": approval_request_count,
                "payload": report,
            },
        )
        self._persist("adaptive_reviews", report)
        return report

    def export_adaptive_memory(self, path: str | Path | None = None) -> None:
        target = Path(path) if path is not None else (self.store.root if self.store is not None else None)
        if target is None:
            raise ValueError("export path is required when no store_path was configured")
        target.mkdir(parents=True, exist_ok=True)
        self.strategy_bandit.export_json(target / "strategy_bandit.json")
        if self.store is None:
            store = AdaptiveJsonStore(target)
            for workflow_id in self._profiles:
                store.append_many("workflow_history", self.workflow_history(workflow_id))
            for entry in self.policy_patch_history_entries():
                store.append("policy_patches", entry)
