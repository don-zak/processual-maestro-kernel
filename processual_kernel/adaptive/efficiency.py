from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from ..adaptive_types import (
    AdaptiveEfficiencyReport,
    AdaptiveEncryptedReportIndex,
    AdaptiveEvidenceDelta,
    AdaptiveEvidenceDigest,
    AdaptiveUiSnapshot,
    AdaptiveWorkloadBudgetDecision,
    AutoOutcomeReport,
    CheckpointBackpressureHint,
    CheckpointCoalescingDecision,
    CheckpointKind,
    CheckpointScheduleDecision,
    OutcomeSweepPlan,
    RuntimeCommand,
    RuntimeCommandBatchPlan,
    RuntimeCommandConflictPlan,
    RuntimeCommandDeduplicationResult,
    RuntimeCommandResult,
    RuntimeCommandThrottlePlan,
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


class AdaptiveEfficiencyGovernor:
    """Read-only efficiency guardrails for adaptive operations.

    This governor reduces duplicate governance work without weakening safety. It never creates checkpoints,
    mutates the kernel, or changes policy thresholds; it only coalesces redundant checkpoint due signals and
    fingerprints runtime commands so host runtimes can keep execution idempotent.
    """

    NON_COALESCABLE_EVENTS = {"critical_agent_failure", "human_escalation"}

    @staticmethod
    def command_fingerprint(command: RuntimeCommand, idempotency_key: str | None = None) -> str:
        if idempotency_key:
            return f"explicit:{idempotency_key}"
        payload = {
            "workflow_id": command.workflow_id,
            "action": command.action.value,
            "subject": command.subject,
            "reason": command.reason,
            "payload": _safe_dict(command.payload),
            "dry_run": command.dry_run,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def coalesce_checkpoint_decision(
        self,
        decision: CheckpointScheduleDecision,
        previous_decision: CheckpointScheduleDecision | None = None,
        *,
        cooldown_seconds: float = 0.0,
    ) -> CheckpointCoalescingDecision:
        if cooldown_seconds <= 0 or previous_decision is None or not decision.due:
            return CheckpointCoalescingDecision(
                workflow_id=decision.workflow_id,
                original_decision=decision,
                effective_decision=decision,
                coalesced=False,
                reason="checkpoint coalescing disabled or not applicable",
                cooldown_seconds=cooldown_seconds,
            )
        if decision.trigger == CheckpointKind.FINAL or decision.event in self.NON_COALESCABLE_EVENTS:
            return CheckpointCoalescingDecision(
                workflow_id=decision.workflow_id,
                original_decision=decision,
                effective_decision=decision,
                coalesced=False,
                reason="final or critical event checkpoints are never coalesced",
                cooldown_seconds=cooldown_seconds,
            )
        if not previous_decision.due:
            return CheckpointCoalescingDecision(
                workflow_id=decision.workflow_id,
                original_decision=decision,
                effective_decision=decision,
                coalesced=False,
                reason="previous checkpoint schedule decision was not due",
                cooldown_seconds=cooldown_seconds,
            )
        same_trigger = previous_decision.trigger == decision.trigger
        same_event = previous_decision.event == decision.event
        within_window = (decision.created_at - previous_decision.created_at) <= cooldown_seconds
        if same_trigger and same_event and within_window:
            effective = CheckpointScheduleDecision(
                workflow_id=decision.workflow_id,
                due=False,
                trigger=decision.trigger,
                reason=f"coalesced duplicate checkpoint within {cooldown_seconds:.0f}s cooldown",
                last_checkpoint_at=decision.last_checkpoint_at,
                next_due_at=decision.next_due_at,
                event=decision.event,
                milestone=decision.milestone,
                final=decision.final,
            )
            return CheckpointCoalescingDecision(
                workflow_id=decision.workflow_id,
                original_decision=decision,
                effective_decision=effective,
                coalesced=True,
                reason=effective.reason,
                cooldown_seconds=cooldown_seconds,
            )
        return CheckpointCoalescingDecision(
            workflow_id=decision.workflow_id,
            original_decision=decision,
            effective_decision=decision,
            coalesced=False,
            reason="checkpoint is distinct or outside coalescing window",
            cooldown_seconds=cooldown_seconds,
        )

    def deduplicate_runtime_command(
        self,
        command: RuntimeCommand,
        seen_fingerprints: set[str],
        *,
        idempotency_key: str | None = None,
        prevent_duplicate: bool = True,
    ) -> RuntimeCommandDeduplicationResult:
        fingerprint = self.command_fingerprint(command, idempotency_key=idempotency_key)
        duplicate = prevent_duplicate and not command.dry_run and fingerprint in seen_fingerprints
        if duplicate:
            reason = "duplicate non-dry-run runtime command suppressed by idempotency guard"
        elif command.dry_run:
            reason = "dry-run command is not recorded as a mutating idempotency key"
        else:
            reason = "runtime command is unique for this workflow and payload"
        return RuntimeCommandDeduplicationResult(
            workflow_id=command.workflow_id,
            command_fingerprint=fingerprint,
            duplicate=duplicate,
            suppressed=duplicate,
            reason=reason,
            action=command.action,
        )

    def checkpoint_backpressure_hint(
        self,
        decision: CheckpointScheduleDecision,
        coalescing: CheckpointCoalescingDecision | None = None,
        *,
        min_poll_seconds: float = 5.0,
        max_poll_seconds: float = 300.0,
        now: float | None = None,
    ) -> CheckpointBackpressureHint:
        """Recommend the next safe schedule poll without creating checkpoints.

        Backpressure is advisory only: final and critical event checkpoints remain immediate.
        """
        import time as _time

        now = _time.time() if now is None else now
        if decision.final or decision.event in self.NON_COALESCABLE_EVENTS:
            return CheckpointBackpressureHint(
                workflow_id=decision.workflow_id,
                active=False,
                recommended_delay_seconds=0.0,
                next_safe_check_at=now,
                reason="final or critical event checkpoints bypass backpressure",
                trigger=decision.trigger,
                event=decision.event,
                coalesced=bool(coalescing and coalescing.coalesced),
            )
        if coalescing is not None and coalescing.coalesced:
            delay = max(min_poll_seconds, min(max_poll_seconds, coalescing.cooldown_seconds))
            return CheckpointBackpressureHint(
                workflow_id=decision.workflow_id,
                active=True,
                recommended_delay_seconds=delay,
                next_safe_check_at=decision.created_at + delay,
                reason="duplicate checkpoint signal is under coalescing backpressure",
                trigger=decision.trigger,
                event=decision.event,
                coalesced=True,
            )
        if not decision.due and decision.next_due_at is not None and decision.next_due_at > now:
            delay = max(min_poll_seconds, min(max_poll_seconds, decision.next_due_at - now))
            return CheckpointBackpressureHint(
                workflow_id=decision.workflow_id,
                active=True,
                recommended_delay_seconds=delay,
                next_safe_check_at=now + delay,
                reason="checkpoint interval has not elapsed; defer schedule polling",
                trigger=decision.trigger,
                event=decision.event,
                coalesced=False,
            )
        return CheckpointBackpressureHint(
            workflow_id=decision.workflow_id,
            active=False,
            recommended_delay_seconds=0.0,
            next_safe_check_at=now,
            reason="checkpoint signal is actionable now" if decision.due else "no checkpoint backpressure needed",
            trigger=decision.trigger,
            event=decision.event,
            coalesced=False,
        )

    def plan_runtime_command_batch(
        self,
        workflow_id: str,
        commands: Iterable[RuntimeCommand],
        seen_fingerprints: set[str],
        *,
        max_mutating_commands: int = 1,
        prevent_duplicate: bool = True,
        idempotency_keys: Iterable[str | None] = (),
    ) -> RuntimeCommandBatchPlan:
        command_items = tuple(commands)
        key_items = tuple(idempotency_keys)
        reasons: list[str] = []
        fingerprints: list[str] = []
        allowed = 0
        suppressed = 0
        mutating_allowed = 0
        for index, command in enumerate(command_items):
            key = key_items[index] if index < len(key_items) else None
            fingerprint = self.command_fingerprint(command, idempotency_key=key)
            fingerprints.append(fingerprint)
            duplicate = prevent_duplicate and not command.dry_run and fingerprint in seen_fingerprints
            mutating = not command.dry_run
            if duplicate:
                suppressed += 1
                reasons.append(f"command {index} suppressed as duplicate")
                continue
            if mutating and mutating_allowed >= max(0, max_mutating_commands):
                suppressed += 1
                reasons.append(f"command {index} suppressed by mutating batch limit")
                continue
            allowed += 1
            if mutating:
                mutating_allowed += 1
        if not reasons:
            reasons.append("runtime command batch is within dedupe and mutating limits")
        return RuntimeCommandBatchPlan(
            workflow_id=workflow_id,
            input_count=len(command_items),
            allowed_count=allowed,
            suppressed_count=suppressed,
            max_mutating_commands=max_mutating_commands,
            fingerprints=tuple(fingerprints),
            reasons=tuple(reasons),
        )

    def plan_runtime_command_conflicts(
        self,
        workflow_id: str,
        commands: Iterable[RuntimeCommand],
        *,
        protect_subjects: bool = True,
    ) -> RuntimeCommandConflictPlan:
        """Suppress conflicting mutating runtime commands before execution.

        The plan is advisory and conservative: read-only/dry-run commands are allowed, while multiple
        mutating state changes for the same subject keep only the highest-priority action.
        """
        command_items = tuple(commands)
        state_priority = {
            "escalate": 100,
            "finalize": 90,
            "pause": 80,
            "reroute": 70,
            "archive": 60,
            "quarantine": 55,
            "reactivate": 50,
            "retry": 40,
            "parallelize": 35,
            "handoff": 30,
            "delegate": 25,
            "merge": 20,
            "observe": 0,
        }
        mutating_indices = [index for index, command in enumerate(command_items) if not command.dry_run]
        allowed = set(range(len(command_items)))
        suppressed: set[int] = set()
        reasons: list[str] = []
        primary_action = None

        if len(mutating_indices) > 1:
            groups: dict[str, list[int]] = {}
            for index in mutating_indices:
                subject_key = command_items[index].subject if protect_subjects else "*"
                groups.setdefault(subject_key, []).append(index)
            for subject, indices in groups.items():
                if len(indices) <= 1:
                    continue
                winner = max(indices, key=lambda i: (state_priority.get(command_items[i].action.value, 10), -i))
                primary_action = command_items[winner].action
                for index in indices:
                    if index == winner:
                        continue
                    suppressed.add(index)
                    allowed.discard(index)
                reasons.append(
                    f"subject {subject} has {len(indices)} mutating commands; kept {command_items[winner].action.value}"
                )

        if not reasons:
            reasons.append("runtime command set has no conflicting mutating commands")

        return RuntimeCommandConflictPlan(
            workflow_id=workflow_id,
            input_count=len(command_items),
            allowed_indices=tuple(sorted(allowed)),
            suppressed_indices=tuple(sorted(suppressed)),
            primary_action=primary_action,
            conflicting_count=len(suppressed),
            reasons=tuple(reasons),
        )

    def plan_runtime_command_throttle(
        self,
        workflow_id: str,
        commands: Iterable[RuntimeCommand],
        *,
        recent_commands: Iterable[Any] = (),
        cooldown_seconds: float = 0.0,
        now: float | None = None,
        protected_actions: Iterable[Any] = (),
    ) -> RuntimeCommandThrottlePlan:
        """Suppress rapid repeated mutating actions even when payloads differ.

        This is stronger than exact de-duplication and more conservative than conflict planning. It is advisory by
        default and only affects mutable commands. Escalate/finalize are protected unless explicitly overridden.
        """
        import time as _time

        now = _time.time() if now is None else now
        command_items = tuple(commands)
        default_protected = {"escalate", "finalize"}
        protected_values = {getattr(action, "value", str(action)) for action in protected_actions} or default_protected
        allowed: set[int] = set()
        suppressed: set[int] = set()
        reasons: list[str] = []
        last_seen_by_key: dict[tuple[str, str], float] = {}

        for item in recent_commands:
            action = getattr(item, "action", None)
            action_value = getattr(action, "value", str(action)) if action is not None else "unknown"
            subject = getattr(item, "subject", None)
            if subject is None:
                payload = getattr(item, "event_payload", {}) or {}
                subject = payload.get("subject") or payload.get("workflow_id") or getattr(item, "workflow_id", "*")
            created_at = float(getattr(item, "created_at", 0.0) or 0.0)
            if cooldown_seconds <= 0 or now - created_at <= cooldown_seconds:
                key = (action_value, str(subject))
                last_seen_by_key[key] = max(created_at, last_seen_by_key.get(key, 0.0))

        for index, command in enumerate(command_items):
            action_value = command.action.value
            subject = str(command.subject)
            key = (action_value, subject)
            if command.dry_run:
                allowed.add(index)
                reasons.append(f"command {index} allowed because dry-run commands do not mutate runtime state")
                continue
            if action_value in protected_values:
                allowed.add(index)
                reasons.append(f"command {index} allowed because {action_value} is protected from throttling")
                last_seen_by_key[key] = now
                continue
            if cooldown_seconds <= 0:
                allowed.add(index)
                reasons.append(f"command {index} allowed because throttling is disabled")
                last_seen_by_key[key] = now
                continue
            last_seen_at = last_seen_by_key.get(key)
            if last_seen_at is not None and now - last_seen_at < cooldown_seconds:
                suppressed.add(index)
                reasons.append(f"command {index} suppressed by {cooldown_seconds:.0f}s action/subject throttle")
                continue
            allowed.add(index)
            last_seen_by_key[key] = now

        if not command_items:
            reasons.append("no runtime commands to throttle")
        return RuntimeCommandThrottlePlan(
            workflow_id=workflow_id,
            input_count=len(command_items),
            allowed_indices=tuple(sorted(allowed)),
            suppressed_indices=tuple(sorted(suppressed)),
            cooldown_seconds=cooldown_seconds,
            protected_actions=tuple(
                command.action for command in command_items if command.action.value in protected_values
            ),
            throttle_key_count=len(last_seen_by_key),
            reasons=tuple(reasons),
        )

    def evidence_delta_digest(
        self,
        previous: AdaptiveEvidenceDigest,
        current: AdaptiveEvidenceDigest,
    ) -> AdaptiveEvidenceDelta:
        """Compare two evidence digests so reviewers can inspect only changed artifacts."""
        previous_keys = set(previous.artifact_checksums)
        current_keys = set(current.artifact_checksums)
        added = tuple(sorted(current_keys - previous_keys))
        removed = tuple(sorted(previous_keys - current_keys))
        common = previous_keys & current_keys
        changed = tuple(
            sorted(key for key in common if previous.artifact_checksums[key] != current.artifact_checksums[key])
        )
        unchanged = tuple(
            sorted(key for key in common if previous.artifact_checksums[key] == current.artifact_checksums[key])
        )
        if previous.stable_checksum == current.stable_checksum:
            reason = "evidence pack is unchanged"
        elif not changed and not added and not removed and previous.counts_checksum != current.counts_checksum:
            reason = "only evidence counts changed"
        else:
            reason = "evidence pack changed; inspect changed, added, or removed artifacts"
        return AdaptiveEvidenceDelta(
            workflow_id=current.workflow_id,
            previous_checksum=previous.stable_checksum,
            current_checksum=current.stable_checksum,
            changed_artifacts=changed,
            added_artifacts=added,
            removed_artifacts=removed,
            unchanged_artifacts=unchanged,
            changed_count=len(changed) + len(added) + len(removed),
            unchanged_count=len(unchanged),
            reason=reason,
        )

    def evidence_pack_digest(
        self,
        pack,
        *,
        omit_artifacts: Iterable[str] = (),
    ) -> AdaptiveEvidenceDigest:
        """Create a stable digest for a full evidence pack without removing source evidence."""
        omitted = tuple(omit_artifacts)
        artifact_checksums: dict[str, str] = {}
        warnings: list[str] = []
        for key, value in sorted(pack.artifacts.items()):
            if key in omitted:
                continue
            canonical = json.dumps(_safe_dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            artifact_checksums[key] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        counts_canonical = json.dumps(
            _safe_dict(pack.counts), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        counts_checksum = hashlib.sha256(counts_canonical.encode("utf-8")).hexdigest()
        stable_payload = {
            "workflow_id": pack.workflow_id,
            "source_schema_version": pack.schema_version,
            "counts_checksum": counts_checksum,
            "artifact_checksums": artifact_checksums,
        }
        stable_canonical = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        stable_checksum = hashlib.sha256(stable_canonical.encode("utf-8")).hexdigest()
        missing_keys = tuple(
            key
            for key in pack.counts
            if key not in pack.artifacts
            and key
            not in {
                "operating_contracts",
                "contract_validations",
                "convergence_reports",
                "recovery_playbooks",
                "evidence_pack_validations",
            }
        )
        if missing_keys:
            warnings.append("some count keys are represented by singular artifacts or optional evidence")
        return AdaptiveEvidenceDigest(
            workflow_id=pack.workflow_id,
            source_schema_version=pack.schema_version,
            digest_schema_version="adaptive-evidence-digest-1.8.0",
            artifact_count=len(artifact_checksums),
            artifact_checksums=artifact_checksums,
            counts_checksum=counts_checksum,
            stable_checksum=stable_checksum,
            omitted_artifacts=omitted,
            warnings=tuple(warnings),
        )

    def encrypted_report_index(
        self,
        workflow_id: str,
        encrypted_reports: Iterable[Any],
    ) -> AdaptiveEncryptedReportIndex:
        """Create a lightweight review index for encrypted reports without decrypting them."""
        items = tuple(encrypted_reports)
        report_kinds = tuple(str(getattr(item, "report_kind", "unknown")) for item in items)
        key_ids = tuple(str(getattr(item, "key_id", "unknown")) for item in items)
        ciphertext_hashes = tuple(str(getattr(item, "ciphertext_sha256", "")) for item in items)
        latest = max((float(getattr(item, "created_at", 0.0) or 0.0) for item in items), default=None)
        warnings: list[str] = []
        if not items:
            warnings.append("no encrypted adaptive reports are currently indexed")
        if len(set(ciphertext_hashes)) < len(ciphertext_hashes):
            warnings.append("duplicate ciphertext hashes detected; verify report idempotency")
        return AdaptiveEncryptedReportIndex(
            workflow_id=workflow_id,
            encrypted_count=len(items),
            report_kinds=report_kinds,
            key_ids=key_ids,
            ciphertext_sha256=ciphertext_hashes,
            latest_created_at=latest,
            warnings=tuple(warnings),
        )

    def ui_snapshot_from_evidence_pack(
        self,
        pack,
        *,
        digest: AdaptiveEvidenceDigest | None = None,
        encrypted_index: AdaptiveEncryptedReportIndex | None = None,
        max_recommendations: int = 6,
    ) -> AdaptiveUiSnapshot:
        """Build a compact UI-safe snapshot from a full evidence pack."""
        artifacts = getattr(pack, "artifacts", {}) or {}
        profile = artifacts.get("profile") or {}
        policy = artifacts.get("policy") or {}
        quality_gate = artifacts.get("quality_gate") or {}
        invariants = artifacts.get("runtime_invariants") or {}
        metrics = artifacts.get("metrics") or {}
        status_parts: list[str] = []
        if quality_gate.get("passed") is True:
            status_parts.append("quality-gate:passed")
        elif quality_gate:
            status_parts.append("quality-gate:attention")
        if invariants.get("passed") is True:
            status_parts.append("invariants:passed")
        elif invariants:
            status_parts.append("invariants:attention")
        status = " | ".join(status_parts) if status_parts else "review-ready"
        recommendations: list[str] = []
        for source_key in ("efficiency_reports", "runtime_invariants", "quality_gate", "convergence_report"):
            value = artifacts.get(source_key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        recommendations.extend(str(x) for x in item.get("recommendations", ()) if x)
                        recommendations.extend(str(x) for x in item.get("warnings", ()) if x)
            elif isinstance(value, dict):
                recommendations.extend(str(x) for x in value.get("recommendations", ()) if x)
                recommendations.extend(str(x) for x in value.get("warnings", ()) if x)
        if not recommendations and metrics:
            recommendations.append("review metrics snapshot before changing runtime mode")
        counts = {str(k): int(v) for k, v in (getattr(pack, "counts", {}) or {}).items()}
        encrypted_count = (
            encrypted_index.encrypted_count if encrypted_index is not None else counts.get("encrypted_reports", 0)
        )
        warnings: list[str] = []
        if encrypted_count == 0:
            warnings.append("no encrypted reports are attached to this snapshot")
        if digest is None:
            warnings.append("snapshot has no evidence digest checksum")
        return AdaptiveUiSnapshot(
            workflow_id=str(getattr(pack, "workflow_id", "unknown")),
            title="Maestro Adaptive Governance Review",
            status=status,
            risk=str(profile.get("risk", "unknown")),
            policy_name=str(policy.get("name", "unknown")),
            runtime_mode=str(policy.get("runtime_mode", "unknown")),
            counts=counts,
            digest_checksum=digest.stable_checksum if digest is not None else None,
            encrypted_report_count=encrypted_count,
            latest_encrypted_report_at=encrypted_index.latest_created_at if encrypted_index is not None else None,
            top_recommendations=tuple(dict.fromkeys(recommendations))[:max_recommendations],
            warnings=tuple(warnings),
        )

    def plan_outcome_sweep(
        self,
        workflow_id: str,
        pending_count: int,
        *,
        max_batch_size: int | None = None,
        min_age_seconds: float = 0.0,
        pending_entries: Iterable[Any] = (),
        now: float | None = None,
    ) -> OutcomeSweepPlan:
        """Plan a bounded outcome sweep and select oldest due decisions first.

        The plan is read-only. When pending_entries are provided, fresh decisions are deferred instead of
        consuming batch slots, which reduces repeated no-op sweeps under long-running workflows.
        """
        import time as _time

        if pending_count <= 0:
            return OutcomeSweepPlan(
                workflow_id=workflow_id,
                pending_count=0,
                batch_size=0,
                remaining_count=0,
                max_batch_size=max_batch_size or 0,
                min_age_seconds=min_age_seconds,
                due_count=0,
                deferred_count=0,
                selected_decision_ids=(),
                reason="no pending outcomes to evaluate",
            )

        batch_limit = pending_count if max_batch_size is None or max_batch_size <= 0 else max_batch_size
        entries = tuple(pending_entries)
        if entries:
            now = _time.time() if now is None else now
            if min_age_seconds <= 0:
                due_entries = list(entries)
            else:
                due_entries = [
                    entry for entry in entries if now - float(getattr(entry, "created_at", now)) >= min_age_seconds
                ]
            due_entries.sort(key=lambda entry: float(getattr(entry, "created_at", 0.0)))
            selected = tuple(due_entries[:batch_limit])
            selected_ids = tuple(
                str(getattr(entry, "decision_id", "")) for entry in selected if getattr(entry, "decision_id", None)
            )
            deferred_count = max(0, len(entries) - len(due_entries))
            remaining_count = max(0, pending_count - len(selected))
            if selected_ids and remaining_count:
                reason = "priority outcome sweep selected oldest due decisions and left bounded remainder"
            elif selected_ids:
                reason = "priority outcome sweep selected all due pending decisions"
            elif deferred_count:
                reason = "all pending outcomes are younger than the minimum age window"
            else:
                reason = "no due pending outcomes selected"
            return OutcomeSweepPlan(
                workflow_id=workflow_id,
                pending_count=pending_count,
                batch_size=len(selected_ids),
                remaining_count=remaining_count,
                max_batch_size=batch_limit,
                min_age_seconds=min_age_seconds,
                due_count=len(due_entries),
                deferred_count=deferred_count,
                selected_decision_ids=selected_ids,
                reason=reason,
            )

        if max_batch_size is None or max_batch_size <= 0:
            batch_size = pending_count
            reason = "evaluate all pending outcomes in one sweep"
        else:
            batch_size = min(pending_count, max_batch_size)
            reason = (
                "outcome sweep batched to reduce adaptive workload"
                if batch_size < pending_count
                else "pending outcomes fit within batch limit"
            )
        return OutcomeSweepPlan(
            workflow_id=workflow_id,
            pending_count=pending_count,
            batch_size=batch_size,
            remaining_count=max(0, pending_count - batch_size),
            max_batch_size=max_batch_size or pending_count,
            min_age_seconds=min_age_seconds,
            due_count=batch_size,
            deferred_count=0,
            selected_decision_ids=(),
            reason=reason,
        )

    def workload_budget_decision(
        self,
        workflow_id: str,
        operation: str,
        *,
        used_count: int,
        limit: int,
        cost_units: int = 1,
    ) -> AdaptiveWorkloadBudgetDecision:
        """Gate expensive adaptive operations with an explicit per-workflow workload budget.

        This never authorizes risky runtime actions by itself; it only prevents optional adaptive work from
        expanding unboundedly when evidence is noisy or repeated.
        """
        safe_limit = max(0, int(limit))
        safe_cost = max(1, int(cost_units))
        used = max(0, int(used_count))
        allowed = used + safe_cost <= safe_limit
        remaining = max(0, safe_limit - used - (safe_cost if allowed else 0))
        if allowed:
            reason = "adaptive workload budget allows this optional operation"
        elif safe_limit == 0:
            reason = "adaptive workload budget disabled this optional operation"
        else:
            reason = "adaptive workload budget exhausted; defer optional operation"
        return AdaptiveWorkloadBudgetDecision(
            workflow_id=workflow_id,
            operation=str(operation),
            allowed=allowed,
            used_count=used,
            limit=safe_limit,
            cost_units=safe_cost,
            remaining_after=remaining,
            reason=reason,
        )

    def efficiency_report(
        self,
        workflow_id: str,
        checkpoint_coalescing: Iterable[CheckpointCoalescingDecision] = (),
        runtime_deduplication: Iterable[RuntimeCommandDeduplicationResult] = (),
        runtime_results: Iterable[RuntimeCommandResult] = (),
        auto_outcomes: Iterable[AutoOutcomeReport] = (),
        checkpoint_backpressure: Iterable[CheckpointBackpressureHint] = (),
        runtime_batches: Iterable[RuntimeCommandBatchPlan] = (),
        outcome_sweep_plans: Iterable[OutcomeSweepPlan] = (),
        workload_budgets: Iterable[AdaptiveWorkloadBudgetDecision] = (),
        runtime_conflicts: Iterable[RuntimeCommandConflictPlan] = (),
        evidence_digests: Iterable[AdaptiveEvidenceDigest] = (),
        runtime_throttles: Iterable[RuntimeCommandThrottlePlan] = (),
        evidence_deltas: Iterable[AdaptiveEvidenceDelta] = (),
        encrypted_reports: Iterable[Any] = (),
        encrypted_report_indexes: Iterable[Any] = (),
        ui_snapshots: Iterable[Any] = (),
    ) -> AdaptiveEfficiencyReport:
        coalescing_items = tuple(checkpoint_coalescing)
        dedupe_items = tuple(runtime_deduplication)
        result_items = tuple(runtime_results)
        outcome_items = tuple(auto_outcomes)
        backpressure_items = tuple(checkpoint_backpressure)
        batch_items = tuple(runtime_batches)
        sweep_items = tuple(outcome_sweep_plans)
        budget_items = tuple(workload_budgets)
        conflict_items = tuple(runtime_conflicts)
        digest_items = tuple(evidence_digests)
        throttle_items = tuple(runtime_throttles)
        delta_items = tuple(evidence_deltas)
        encrypted_items = tuple(encrypted_reports)
        encrypted_index_items = tuple(encrypted_report_indexes)
        ui_snapshot_items = tuple(ui_snapshots)
        recommendations: list[str] = []
        if sum(1 for item in coalescing_items if item.coalesced) > 0:
            recommendations.append("keep checkpoint coalescing enabled to avoid duplicate adaptive cycles")
        if sum(1 for item in backpressure_items if item.active) > 0:
            recommendations.append("honor checkpoint backpressure hints before re-polling schedule state")
        if sum(1 for item in dedupe_items if item.duplicate) > 0:
            recommendations.append("keep runtime command idempotency keys stable across retries")
        runtime_batch_suppressed = sum(item.suppressed_count for item in batch_items)
        if runtime_batch_suppressed > 0:
            recommendations.append("keep mutating runtime command batches small and idempotent")
        skipped = sum(item.skipped_count for item in outcome_items)
        if skipped > 0:
            recommendations.append("re-run outcome sweep after the minimum age window expires")
        if sum(item.remaining_count for item in sweep_items) > 0:
            recommendations.append("continue outcome sweeps in bounded batches until coverage is complete")
        if sum(item.deferred_count for item in sweep_items) > 0:
            recommendations.append("respect outcome age windows and retry deferred outcomes later")
        runtime_conflict_suppressed = sum(item.conflicting_count for item in conflict_items)
        if runtime_conflict_suppressed > 0:
            recommendations.append("resolve conflicting runtime recommendations before executing mutating commands")
        if sum(1 for item in budget_items if not item.allowed) > 0:
            recommendations.append("defer optional adaptive work until workload budget is replenished")
        if digest_items:
            recommendations.append("use evidence digests for lightweight review before opening full artifacts")
        runtime_throttle_suppressed = sum(len(item.suppressed_indices) for item in throttle_items)
        if runtime_throttle_suppressed > 0:
            recommendations.append("honor runtime command throttle plans to avoid rapid mutable action churn")
        if delta_items:
            recommendations.append("use evidence deltas to review only changed artifacts between evidence packs")
        if encrypted_items:
            recommendations.append("keep sensitive adaptive reports encrypted with externally managed AES-256 keys")
        if encrypted_index_items:
            recommendations.append("use encrypted report indexes for lightweight review without decrypting reports")
        if ui_snapshot_items:
            recommendations.append("use UI snapshots for safe offline review before opening full evidence packs")
        if not recommendations:
            recommendations.append("efficiency guardrails found no duplicate adaptive work")
        return AdaptiveEfficiencyReport(
            workflow_id=workflow_id,
            checkpoint_coalesced_count=sum(1 for item in coalescing_items if item.coalesced),
            duplicate_runtime_command_count=sum(1 for item in dedupe_items if item.duplicate),
            runtime_command_count=len(result_items),
            auto_outcome_evaluated_count=sum(item.evaluated_count for item in outcome_items),
            auto_outcome_skipped_count=skipped,
            checkpoint_backpressure_count=sum(1 for item in backpressure_items if item.active),
            runtime_batch_suppressed_count=runtime_batch_suppressed,
            runtime_conflict_suppressed_count=runtime_conflict_suppressed,
            outcome_sweep_planned_count=sum(item.batch_size for item in sweep_items),
            outcome_sweep_deferred_count=sum(item.deferred_count for item in sweep_items),
            workload_budget_blocked_count=sum(1 for item in budget_items if not item.allowed),
            evidence_digest_count=len(digest_items),
            runtime_throttle_suppressed_count=runtime_throttle_suppressed,
            evidence_delta_count=len(delta_items),
            encrypted_report_count=len(encrypted_items),
            encrypted_report_index_count=len(encrypted_index_items),
            ui_snapshot_count=len(ui_snapshot_items),
            recommendations=tuple(recommendations),
        )
