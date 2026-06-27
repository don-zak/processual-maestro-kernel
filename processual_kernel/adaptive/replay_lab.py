from __future__ import annotations

from collections.abc import Iterable

from ..adaptive_types import (
    CounterfactualReplayResult,
    DecisionOutcome,
    PolicyProfile,
    ReplayComparison,
    WorkflowHistoryEvent,
)
from ..types import MaestroAction


class ReplayLab:
    """Offline policy A/B and counterfactual review lab.

    The lab never executes live agents. It replays recorded decisions/history with simple, transparent assumptions so
    candidate policies can be reviewed before any production adaptation.
    """

    def compare(
        self,
        workflow_id: str,
        baseline: PolicyProfile,
        candidate: PolicyProfile,
        baseline_outcomes: Iterable[DecisionOutcome],
        candidate_outcomes: Iterable[DecisionOutcome],
    ) -> ReplayComparison:
        b = list(baseline_outcomes)
        c = list(candidate_outcomes)
        b_quality = self._avg([x.decision_quality for x in b])
        c_quality = self._avg([x.decision_quality for x in c])
        b_cost = self._avg([x.cost_delta for x in b])
        c_cost = self._avg([x.cost_delta for x in c])
        b_latency = self._avg([x.latency_delta for x in b])
        c_latency = self._avg([x.latency_delta for x in c])
        return self._comparison_from_deltas(
            workflow_id,
            baseline,
            candidate,
            c_quality - b_quality,
            c_cost - b_cost,
            c_latency - b_latency,
            min(len(b), len(c)),
        )

    def replay_history(
        self,
        workflow_id: str,
        baseline: PolicyProfile,
        candidate: PolicyProfile,
        history: Iterable[WorkflowHistoryEvent],
    ) -> ReplayComparison:
        """Replay workflow history under a candidate policy using conservative counterfactual assumptions."""
        events = list(history)
        quality_delta = 0.0
        cost_delta = 0.0
        latency_delta = 0.0
        retry_seen = 0
        handoff_degradation_seen = 0
        escalation_seen = 0

        for event in events:
            quality_delta += event.quality_delta
            cost_delta += event.cost_delta
            latency_delta += event.latency_delta
            if event.action == MaestroAction.RETRY:
                retry_seen += 1
                if retry_seen > candidate.max_retries:
                    cost_delta -= 0.08
                    latency_delta -= 0.08
                    quality_delta -= 0.02
            elif event.action == MaestroAction.REROUTE:
                if candidate.kernel_policy.min_edge_psi >= baseline.kernel_policy.min_edge_psi:
                    quality_delta += 0.04
                    latency_delta -= 0.02
            elif event.action == MaestroAction.ESCALATE:
                escalation_seen += 1
                if candidate.human_gate_required:
                    quality_delta += 0.03
                    cost_delta += 0.02
            if event.event_type in {"weak_handoff", "handoff_degradation"}:
                handoff_degradation_seen += 1

        if handoff_degradation_seen and candidate.kernel_policy.min_edge_psi >= baseline.kernel_policy.min_edge_psi:
            quality_delta += min(0.12, 0.03 * handoff_degradation_seen)
        if escalation_seen == 0 and candidate.human_gate_required:
            quality_delta += 0.01

        samples = max(1, len(events))
        return self._comparison_from_deltas(
            workflow_id,
            baseline,
            candidate,
            quality_delta / samples,
            cost_delta / samples,
            latency_delta / samples,
            samples,
        )

    def counterfactual_scenarios(
        self,
        workflow_id: str,
        baseline: PolicyProfile,
        history: Iterable[WorkflowHistoryEvent],
        candidate_policies: Iterable[PolicyProfile] = (),
    ) -> tuple[CounterfactualReplayResult, ...]:
        """Evaluate the paper's explicit "what if" questions without touching live workflows."""
        events = list(history)
        results = [
            self._early_escalation(workflow_id, events),
            self._remove_extra_retry(workflow_id, baseline, events),
            self._insert_mediator(workflow_id, events),
        ]
        for candidate in candidate_policies:
            if candidate.name == baseline.name:
                continue
            comparison = self.replay_history(workflow_id, baseline, candidate, events)
            results.append(
                CounterfactualReplayResult(
                    workflow_id=workflow_id,
                    scenario=f"policy_swap:{candidate.name.value}",
                    description=f"What if {candidate.name.value} had been used instead of {baseline.name.value}?",
                    quality_delta=comparison.quality_delta,
                    cost_delta=comparison.cost_delta,
                    latency_delta=comparison.latency_delta,
                    recommendation=comparison.recommendation,
                    confidence=comparison.confidence,
                    sample_size=max(1, len(events)),
                )
            )
        return tuple(results)

    def _early_escalation(self, workflow_id: str, events: list[WorkflowHistoryEvent]) -> CounterfactualReplayResult:
        risk_events = [e for e in events if e.event_type in {"repeated_failure", "handoff_degradation", "checkpoint"}]
        quality_delta = min(0.18, 0.035 * len(risk_events))
        cost_delta = 0.025 if risk_events else 0.0
        latency_delta = -min(0.12, 0.025 * len(risk_events))
        return self._scenario_result(
            workflow_id,
            "early_escalation",
            "What if human escalation had happened earlier after risk signals?",
            quality_delta,
            cost_delta,
            latency_delta,
            len(risk_events),
        )

    def _remove_extra_retry(
        self, workflow_id: str, baseline: PolicyProfile, events: list[WorkflowHistoryEvent]
    ) -> CounterfactualReplayResult:
        retry_events = [e for e in events if e.action == MaestroAction.RETRY]
        extra_retries = max(0, len(retry_events) - baseline.max_retries)
        quality_delta = -0.015 * extra_retries
        cost_delta = -0.07 * extra_retries
        latency_delta = -0.07 * extra_retries
        return self._scenario_result(
            workflow_id,
            "remove_extra_retry",
            "What if retry attempts beyond the selected policy limit had been removed?",
            quality_delta,
            cost_delta,
            latency_delta,
            len(retry_events),
        )

    def _insert_mediator(self, workflow_id: str, events: list[WorkflowHistoryEvent]) -> CounterfactualReplayResult:
        degraded = [e for e in events if e.event_type in {"handoff_degradation", "weak_handoff"}]
        quality_delta = min(0.22, 0.055 * len(degraded))
        cost_delta = 0.035 * min(1, len(degraded))
        latency_delta = 0.015 * min(1, len(degraded))
        return self._scenario_result(
            workflow_id,
            "insert_mediator",
            "What if a Synthesizer/Mediator agent had been inserted for weak handoffs?",
            quality_delta,
            cost_delta,
            latency_delta,
            len(degraded),
        )

    def _scenario_result(
        self,
        workflow_id: str,
        scenario: str,
        description: str,
        quality_delta: float,
        cost_delta: float,
        latency_delta: float,
        sample_size: int,
    ) -> CounterfactualReplayResult:
        # Prefer scenarios where quality gain is meaningful and cost/latency penalties are bounded.
        recommendation = (
            "prefer_scenario"
            if quality_delta > 0.03 and cost_delta <= 0.08 and latency_delta <= 0.08
            else "keep_baseline"
        )
        confidence = min(0.9, 0.30 + 0.06 * max(1, sample_size))
        return CounterfactualReplayResult(
            workflow_id=workflow_id,
            scenario=scenario,
            description=description,
            quality_delta=round(quality_delta, 4),
            cost_delta=round(cost_delta, 4),
            latency_delta=round(latency_delta, 4),
            recommendation=recommendation,
            confidence=round(confidence, 4),
            sample_size=max(1, sample_size),
        )

    def _comparison_from_deltas(
        self,
        workflow_id: str,
        baseline: PolicyProfile,
        candidate: PolicyProfile,
        quality_delta: float,
        cost_delta: float,
        latency_delta: float,
        sample_size: int,
    ) -> ReplayComparison:
        recommendation = "prefer_candidate" if quality_delta > 0.03 and cost_delta <= 0.06 else "keep_baseline"
        confidence = min(0.9, 0.35 + 0.05 * sample_size)
        return ReplayComparison(
            workflow_id=workflow_id,
            baseline_policy=baseline.name,
            candidate_policy=candidate.name,
            quality_delta=round(quality_delta, 4),
            cost_delta=round(cost_delta, 4),
            latency_delta=round(latency_delta, 4),
            recommendation=recommendation,
            confidence=round(confidence, 4),
        )

    @staticmethod
    def _avg(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0
