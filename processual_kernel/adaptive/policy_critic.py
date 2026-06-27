from __future__ import annotations

from collections.abc import Iterable

from ..adaptive_types import CheckpointReport, DecisionOutcome, PolicyCritique, PolicyPatch, PolicyProfile, RuntimeMode
from ..types import StepState


class PolicyCritic:
    """Reviews workflow behavior and suggests safe policy patches in recommend mode."""

    def review(
        self,
        kernel,
        workflow_id: str,
        policy: PolicyProfile,
        checkpoints: Iterable[CheckpointReport] = (),
        outcomes: Iterable[DecisionOutcome] = (),
    ) -> PolicyCritique:
        workflow = kernel.get_workflow(workflow_id)
        checkpoint_list = list(checkpoints)
        outcome_list = list(outcomes)
        findings: list[str] = []
        patches: list[PolicyPatch] = []
        exhausted_failures = [
            s for s in workflow.steps.values() if s.state == StepState.FAILED and s.attempts >= s.step.max_retries
        ]
        repeated_retry = [s for s in workflow.steps.values() if s.attempts > 1 and s.state == StepState.FAILED]
        weak_handoff_reports = [r for r in checkpoint_list if any(x.startswith("weak_handoffs") for x in r.risks)]
        low_quality_outcomes = [o for o in outcome_list if o.decision_quality < 0.45]

        if exhausted_failures:
            findings.append("failed steps exhausted retries; reroute or mediator should be considered")
        if repeated_retry:
            findings.append("retry was repeated without recovery on at least one step")
            patches.append(
                self._patch(
                    policy,
                    "max_step_attempts",
                    policy.kernel_policy.max_step_attempts,
                    max(1, policy.kernel_policy.max_step_attempts - 1),
                    "reduce ineffective retry pressure",
                    sample_size=len(repeated_retry),
                )
            )
        if len(weak_handoff_reports) >= 1:
            findings.append("handoff degraded during checkpoint review")
            patches.append(
                self._patch(
                    policy,
                    "min_edge_psi",
                    policy.kernel_policy.min_edge_psi,
                    max(0.0, policy.kernel_policy.min_edge_psi),
                    "tighten weak handoff monitoring",
                    sample_size=len(weak_handoff_reports),
                )
            )
        if low_quality_outcomes:
            findings.append("one or more governance decisions scored below quality threshold")
        if not findings:
            findings.append("policy behavior was stable; no patch recommended")

        confidence = max(0.35, min(0.9, 0.55 + 0.08 * len(checkpoint_list) + 0.03 * len(outcome_list)))
        return PolicyCritique(
            workflow_id=workflow_id,
            policy_name=policy.name,
            policy_version=policy.policy_version,
            findings=tuple(findings),
            suggested_changes=tuple(p for p in patches if p.old_value != p.new_value),
            confidence=round(confidence, 4),
        )

    @staticmethod
    def _patch(policy: PolicyProfile, field: str, old_value, new_value, reason: str, sample_size: int) -> PolicyPatch:
        return PolicyPatch(
            field=field,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            policy_version_from=policy.policy_version,
            policy_version_to=f"{policy.policy_version}+patch",
            sample_size=sample_size,
            runtime_mode=RuntimeMode.RECOMMEND,
        )
