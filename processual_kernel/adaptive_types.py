from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .types import KernelPolicy, MaestroAction


class TaskSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class TaskDuration(str, Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AmbiguityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AgentCountBand(str, Enum):
    SINGLE = "single-agent"
    FEW = "few-agents"
    MANY = "many-agents"


class PolicyName(str, Enum):
    FAST = "FastPolicy"
    BALANCED = "BalancedPolicy"
    CONSERVATIVE = "ConservativePolicy"
    LONG_RUNNING = "LongRunningPolicy"
    QUALITY_FIRST = "QualityFirstPolicy"
    COST_SAVING = "CostSavingPolicy"
    EXPLORATORY = "ExploratoryPolicy"
    CRITICAL_SAFETY = "CriticalSafetyPolicy"


class RuntimeMode(str, Enum):
    OBSERVE = "observe"
    RECOMMEND = "recommend"
    CONTROLLED_ADAPTIVE = "controlled_adaptive"
    RESTRICTED_CRITICAL = "restricted_critical"


class CertificationLevel(str, Enum):
    BLOCKED = "blocked"
    OBSERVE_ONLY = "observe_only"
    RECOMMEND_READY = "recommend_ready"
    CONTROLLED_READY = "controlled_ready"
    RESTRICTED_CRITICAL_READY = "restricted_critical_ready"


class CheckpointKind(str, Enum):
    HOURLY = "hourly"
    EVENT_BASED = "event_based"
    MILESTONE = "milestone"
    FINAL = "final"


class ExecutionTempo(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    CAUTIOUS = "cautious"
    INTENSIVE = "intensive"


@dataclass(frozen=True, slots=True)
class TaskProfile:
    size: TaskSize
    duration: TaskDuration
    risk: RiskLevel
    ambiguity: AmbiguityLevel
    agent_count: AgentCountBand
    requires_hourly_checkpoint: bool = False
    requires_audit: bool = True
    budget_sensitivity: RiskLevel = RiskLevel.MEDIUM
    estimated_minutes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PolicyProfile:
    name: PolicyName
    policy_version: str
    kernel_policy: KernelPolicy
    checkpoint_interval_minutes: int | None
    runtime_mode: RuntimeMode
    max_agents: int
    max_retries: int
    parallel_execution: bool
    drift_sensitivity: float
    min_sample_size: int
    human_gate_required: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TempoPlan:
    tempo: ExecutionTempo
    max_agents: int
    max_retries: int
    allow_parallel_execution: bool
    checkpoint_interval_minutes: int | None
    monitor_drift: bool
    budget_stop_threshold: float
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckpointReport:
    workflow_id: str
    kind: CheckpointKind
    checkpoint_number: int
    policy_name: PolicyName
    policy_version: str
    workflow_status: dict[str, Any]
    agent_findings: dict[str, Any]
    handoff_findings: dict[str, Any]
    risks: tuple[str, ...]
    recommended_action: MaestroAction
    confidence: float
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class DecisionOutcome:
    decision_id: str
    action: str
    expected_effect: str
    actual_result: str
    quality_delta: float = 0.0
    cost_delta: float = 0.0
    latency_delta: float = 0.0
    recovery_time_delta: float = 0.0
    success_probability_delta: float = 0.0
    human_feedback_score: float | None = None
    decision_quality: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class PolicyPatch:
    field: str
    old_value: Any
    new_value: Any
    reason: str
    policy_version_from: str
    policy_version_to: str
    sample_size: int
    reversible: bool = True
    runtime_mode: RuntimeMode = RuntimeMode.RECOMMEND
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class PolicyCritique:
    workflow_id: str
    policy_name: PolicyName
    policy_version: str
    findings: tuple[str, ...]
    suggested_changes: tuple[PolicyPatch, ...]
    confidence: float
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class DriftAlert:
    entity_id: str
    entity_type: str
    metric: str
    previous_value: float
    current_value: float
    severity: RiskLevel
    reason: str
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    workflow_id: str
    baseline_policy: PolicyName
    candidate_policy: PolicyName
    quality_delta: float
    cost_delta: float
    latency_delta: float
    recommendation: str
    confidence: float


@dataclass(frozen=True, slots=True)
class StrategySuggestion:
    strategy: MaestroAction
    confidence: float
    sample_size: int
    reason: str
    safe_to_apply: bool


@dataclass(frozen=True, slots=True)
class HandoffSchemaSuggestion:
    edge_id: str
    required_fields: tuple[str, ...]
    validation_rules: tuple[str, ...]
    summary_format: str
    checklist: tuple[str, ...]
    recommend_mediator: bool
    confidence: float
    reason: str


@dataclass(frozen=True, slots=True)
class HandoffValidationResult:
    edge_id: str
    valid: bool
    missing_fields: tuple[str, ...] = ()
    failed_rules: tuple[str, ...] = ()
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class WorkflowHistoryEvent:
    workflow_id: str
    event_type: str
    action: MaestroAction | None = None
    policy_name: PolicyName | None = None
    quality_delta: float = 0.0
    cost_delta: float = 0.0
    latency_delta: float = 0.0
    success_probability_delta: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    workflow_success_rate: float
    handoff_failure_rate: float
    recovery_time: float
    cost_per_successful_workflow: float
    false_retry_rate: float
    false_reroute_rate: float
    late_escalation_rate: float
    unnecessary_escalation_rate: float
    agent_bloat_ratio: float
    checkpoint_detection_accuracy: float
    policy_patch_success_rate: float
    outcome_coverage_ratio: float
    workflow_count: int
    decision_outcome_count: int
    checkpoint_count: int
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveQualityGateReport:
    workflow_id: str
    runtime_mode: RuntimeMode
    passed: bool
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    eligible_next_mode: RuntimeMode | None = None
    metrics: MetricsSnapshot | None = None
    pending_outcome_count: int = 0
    pending_approval_count: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeInvariantReport:
    workflow_id: str
    passed: bool
    checked_invariants: tuple[str, ...]
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class HandoffRepairPlan:
    edge_id: str
    suggestion: HandoffSchemaSuggestion
    steps: tuple[str, ...]
    validation_required: bool = True
    mediator_agent_role: str | None = None
    human_review_required: bool = False
    expected_effect: str = "improve handoff quality and reduce rework"
    confidence: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class CounterfactualReplayResult:
    workflow_id: str
    scenario: str
    description: str
    quality_delta: float
    cost_delta: float
    latency_delta: float
    recommendation: str
    confidence: float
    sample_size: int
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class CheckpointScheduleDecision:
    workflow_id: str
    due: bool
    trigger: CheckpointKind | None
    reason: str
    last_checkpoint_at: float | None = None
    next_due_at: float | None = None
    event: str | None = None
    milestone: bool = False
    final: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeCommand:
    workflow_id: str
    action: MaestroAction
    subject: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)
    authorized: bool = False
    requires_human_approval: bool = False
    request_id: str | None = None
    dry_run: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeCommandResult:
    workflow_id: str
    action: MaestroAction
    executed: bool
    dry_run: bool
    authorized: bool
    requires_human_approval: bool
    reason: str
    request_id: str | None = None
    event_payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AutoOutcomeReport:
    workflow_id: str
    evaluated_count: int
    skipped_count: int
    outcome_coverage_ratio: float
    outcomes: tuple[DecisionOutcome, ...] = ()
    reason: str = "auto outcome sweep"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class CheckpointCoalescingDecision:
    workflow_id: str
    original_decision: CheckpointScheduleDecision
    effective_decision: CheckpointScheduleDecision
    coalesced: bool
    reason: str
    cooldown_seconds: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeCommandDeduplicationResult:
    workflow_id: str
    command_fingerprint: str
    duplicate: bool
    suppressed: bool
    reason: str
    action: MaestroAction
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class CheckpointBackpressureHint:
    workflow_id: str
    active: bool
    recommended_delay_seconds: float
    next_safe_check_at: float | None
    reason: str
    trigger: CheckpointKind | None = None
    event: str | None = None
    coalesced: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeCommandBatchPlan:
    workflow_id: str
    input_count: int
    allowed_count: int
    suppressed_count: int
    max_mutating_commands: int
    fingerprints: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeCommandConflictPlan:
    workflow_id: str
    input_count: int
    allowed_indices: tuple[int, ...]
    suppressed_indices: tuple[int, ...]
    primary_action: MaestroAction | None = None
    conflicting_count: int = 0
    reasons: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RuntimeCommandThrottlePlan:
    workflow_id: str
    input_count: int
    allowed_indices: tuple[int, ...]
    suppressed_indices: tuple[int, ...]
    cooldown_seconds: float
    protected_actions: tuple[MaestroAction, ...] = ()
    throttle_key_count: int = 0
    reasons: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class OutcomeSweepPlan:
    workflow_id: str
    pending_count: int
    batch_size: int
    remaining_count: int
    max_batch_size: int
    min_age_seconds: float = 0.0
    due_count: int = 0
    deferred_count: int = 0
    selected_decision_ids: tuple[str, ...] = ()
    reason: str = "outcome sweep plan"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveWorkloadBudgetDecision:
    workflow_id: str
    operation: str
    allowed: bool
    used_count: int
    limit: int
    cost_units: int = 1
    remaining_after: int = 0
    reason: str = "adaptive workload budget decision"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveEfficiencyReport:
    workflow_id: str
    checkpoint_coalesced_count: int
    duplicate_runtime_command_count: int
    runtime_command_count: int
    auto_outcome_evaluated_count: int
    auto_outcome_skipped_count: int
    checkpoint_backpressure_count: int = 0
    runtime_batch_suppressed_count: int = 0
    runtime_conflict_suppressed_count: int = 0
    outcome_sweep_planned_count: int = 0
    outcome_sweep_deferred_count: int = 0
    workload_budget_blocked_count: int = 0
    evidence_digest_count: int = 0
    runtime_throttle_suppressed_count: int = 0
    evidence_delta_count: int = 0
    encrypted_report_count: int = 0
    encrypted_report_index_count: int = 0
    ui_snapshot_count: int = 0
    recommendations: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveCycleReport:
    workflow_id: str
    profile: TaskProfile
    policy: PolicyProfile
    tempo: TempoPlan
    decision_id: str | None = None
    checkpoint: CheckpointReport | None = None
    drift_alerts: tuple[DriftAlert, ...] = ()
    handoff_suggestions: tuple[HandoffSchemaSuggestion, ...] = ()
    policy_critique: PolicyCritique | None = None
    policy_patches: tuple[PolicyPatch, ...] = ()
    strategy_suggestion: StrategySuggestion | None = None
    budget_action: MaestroAction | None = None
    runtime_invariants: RuntimeInvariantReport | None = None
    quality_gate: AdaptiveQualityGateReport | None = None
    operating_contract: OperatingContract | None = None
    contract_validation: OperatingContractValidation | None = None
    convergence_report: AdaptiveConvergenceReport | None = None
    outcome_coverage_ratio: float = 1.0
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveReviewReport:
    workflow_id: str
    final_checkpoint: CheckpointReport | None
    final_critique: PolicyCritique
    metrics: MetricsSnapshot
    quality_gate: AdaptiveQualityGateReport | None = None
    runtime_invariants: RuntimeInvariantReport | None = None
    operating_contract: OperatingContract | None = None
    contract_validation: OperatingContractValidation | None = None
    convergence_report: AdaptiveConvergenceReport | None = None
    recovery_playbook: RecoveryPlaybook | None = None
    evidence_pack_validation: EvidencePackValidationResult | None = None
    replay_comparisons: tuple[ReplayComparison, ...] = ()
    counterfactual_results: tuple[CounterfactualReplayResult, ...] = ()
    pending_outcome_count: int = 0
    patch_history_count: int = 0
    approval_request_count: int = 0
    recommendations: tuple[str, ...] = ()
    integrity_report: AdaptiveIntegrityReport | None = None
    certification_report: AdaptiveCertificationReport | None = None
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class PolicyPatchHistoryEntry:
    patch: PolicyPatch
    status: str
    workflow_id: str | None = None
    reason: str = ""
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveModeTransitionDecision:
    workflow_id: str
    current_mode: RuntimeMode
    requested_mode: RuntimeMode
    allowed: bool
    reason: str
    quality_gate: AdaptiveQualityGateReport
    runtime_invariants: RuntimeInvariantReport
    pending_outcome_count: int = 0
    pending_approval_count: int = 0
    required_human_approval: bool = False
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class PatchVerificationResult:
    workflow_id: str
    patch: PolicyPatch
    status: str
    rollback_recommended: bool
    reason: str
    metrics: MetricsSnapshot
    confidence: float
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class OperatingContract:
    workflow_id: str
    runtime_mode: RuntimeMode
    policy_name: PolicyName
    policy_version: str
    allowed_actions: tuple[MaestroAction, ...]
    human_gate_actions: tuple[MaestroAction, ...]
    forbidden_patch_fields: tuple[str, ...]
    checkpoint_interval_minutes: int | None
    audit_required: bool = True
    min_outcome_coverage: float = 0.95
    max_pending_outcomes: int = 0
    max_pending_approvals: int = 0
    critical_mode_locked: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class OperatingContractValidation:
    workflow_id: str
    contract: OperatingContract
    passed: bool
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class RecoveryPlaybookStep:
    step_id: str
    action: str
    reason: str
    priority: int
    requires_human_approval: bool = False
    expected_effect: str = "improve adaptive governance outcome"
    source: str = "adaptive_review"


@dataclass(frozen=True, slots=True)
class RecoveryPlaybook:
    workflow_id: str
    steps: tuple[RecoveryPlaybookStep, ...]
    confidence: float
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class EvidencePackValidationResult:
    workflow_id: str
    schema_version: str
    valid: bool
    missing_artifacts: tuple[str, ...] = ()
    count_mismatches: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveConvergenceReport:
    workflow_id: str
    stable: bool
    window_size: int
    avg_outcome_coverage: float
    max_violation_count: int
    avg_checkpoint_confidence: float
    recommendation: str
    reasons: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveIntegrityReport:
    workflow_id: str
    schema_version: str
    valid: bool
    checksum: str
    expected_checksum: str | None = None
    artifact_count: int = 0
    count_mismatches: tuple[str, ...] = ()
    missing_artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveCertificationReport:
    workflow_id: str
    level: CertificationLevel
    certified: bool
    reason: str
    evidence_checksum: str
    schema_version: str = "adaptive-certification-1.0.0"
    quality_gate_passed: bool = False
    runtime_invariants_passed: bool = False
    contract_validation_passed: bool = False
    convergence_stable: bool = False
    pending_outcome_count: int = 0
    pending_approval_count: int = 0
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class ActionAuthorizationReport:
    workflow_id: str
    action: MaestroAction
    authorized: bool
    requires_human_approval: bool
    reason: str
    contract_validation: OperatingContractValidation
    request_id: str | None = None
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    executed: bool = False
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveEvidenceDigest:
    workflow_id: str
    source_schema_version: str
    digest_schema_version: str
    artifact_count: int
    artifact_checksums: dict[str, str]
    counts_checksum: str
    stable_checksum: str
    omitted_artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveEvidenceDelta:
    workflow_id: str
    previous_checksum: str
    current_checksum: str
    changed_artifacts: tuple[str, ...]
    added_artifacts: tuple[str, ...] = ()
    removed_artifacts: tuple[str, ...] = ()
    unchanged_artifacts: tuple[str, ...] = ()
    changed_count: int = 0
    unchanged_count: int = 0
    schema_version: str = "adaptive-evidence-delta-1.8.0"
    reason: str = "adaptive evidence delta"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class EncryptedAdaptiveReport:
    workflow_id: str
    report_kind: str
    algorithm: str
    key_id: str
    nonce_b64: str
    aad_b64: str
    ciphertext_b64: str
    plaintext_sha256: str
    ciphertext_sha256: str
    plaintext_schema_version: str
    schema_version: str = "adaptive-report-encryption-1.8.0"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveReportDecryptionResult:
    workflow_id: str
    report_kind: str
    valid: bool
    artifact: dict[str, Any] | None = None
    plaintext_sha256: str | None = None
    ciphertext_sha256: str | None = None
    reason: str = "adaptive report decryption"
    schema_version: str = "adaptive-report-decryption-1.8.0"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveEncryptedReportIndex:
    workflow_id: str
    encrypted_count: int
    report_kinds: tuple[str, ...]
    key_ids: tuple[str, ...]
    ciphertext_sha256: tuple[str, ...]
    latest_created_at: float | None = None
    schema_version: str = "adaptive-encrypted-report-index-1.8.0"
    warnings: tuple[str, ...] = ()
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveUiSnapshot:
    workflow_id: str
    title: str
    status: str
    risk: str
    policy_name: str
    runtime_mode: str
    counts: dict[str, int]
    digest_checksum: str | None = None
    encrypted_report_count: int = 0
    latest_encrypted_report_at: float | None = None
    top_recommendations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    schema_version: str = "adaptive-ui-snapshot-1.8.0"
    created_at: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class AdaptiveEvidencePack:
    workflow_id: str
    counts: dict[str, int]
    artifacts: dict[str, Any]
    schema_version: str = "adaptive-evidence-pack-1.8.0"
    created_at: float = field(default_factory=time.time)
