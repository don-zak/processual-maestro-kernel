"""CGT Governor Gateway — public Governance Genome v2 engine."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from ..security import sign_response
from .governance_context import GovernanceRequestContext
from .lifecycle import lifecycle_engine
from .models import AgentState, EvaluationRecord, GatewayAction, GatewayDecision
from .operation_policies import get_operation_policy, merge_governance_contexts
from .policies import policy_engine
from .qualification import qualification_layer
from .registry import gateway_registry
from .runtime_execution_attestation import (
    RuntimeExecutionAttestation,
    from_runtime_execution_attestation,
    runtime_attestation_issues,
)
from .sufficiency import SufficiencyStatus, TaskSufficiencyEvidence
from .trusted_evidence import (
    TrustedEvidenceBinding,
    TrustedEvidenceProjection,
    trusted_evidence_binding_issues,
)
from .verification import VerificationEvidence, VerificationStatus

logger = logging.getLogger("processual_api.cgt_governor.gateway.engine")


class GatewayEngine:
    """Evaluate a response through hard gates before Fate/rank optimization."""

    @staticmethod
    def evaluate(
        agent_id: str,
        client_query: str,
        agent_response: str,
        language: str = "en",
        verification_evidence: VerificationEvidence | None = None,
        sufficiency_evidence: TaskSufficiencyEvidence | None = None,
        governance_context: GovernanceRequestContext | None = None,
        operation_id: str = "response.evaluate",
        trusted_evidence_projection: TrustedEvidenceProjection | None = None,
        trusted_evidence_binding: TrustedEvidenceBinding | None = None,
        runtime_execution_attestation: RuntimeExecutionAttestation | None = None,
    ) -> GatewayDecision | None:
        agent = gateway_registry.get(agent_id)
        if agent is None:
            logger.warning("Gateway evaluate called for unknown agent: %s", agent_id)
            return None

        if agent.state not in (AgentState.ACTIVE, AgentState.REHABILITATING):
            return GatewayDecision(
                action=GatewayAction.BLOCK,
                rank="",
                reward=0.0,
                policy="",
                policy_label="Agent Not Available",
                fate_vector={},
                repair_prompt=None,
                agent_state=agent.state,
                message=f"Agent is {agent.state.value}. Cannot process requests.",
            )

        from ..analyzer import analyze_cgt
        from ..governor import govern_answer

        scores = analyze_cgt(client_query, agent_response, language=language)
        result = govern_answer(answer=agent_response, **scores, language=language)
        fate_vector = {
            "stability": result.fate.stability,
            "hybridity": result.fate.hybridity,
            "distortion": result.fate.distortion,
            "extinction": result.fate.extinction,
            "collapse": result.fate.collapse,
            "flourishing": result.fate.flourishing,
            "transient": result.fate.transient,
        }

        previous_distance: float | None = None
        previous_component_risks: dict[str, float] | None = None
        if agent.evaluation_history:
            previous = agent.evaluation_history[-1].qualification or {}
            value = previous.get("distance_to_viability")
            if isinstance(value, (int, float)):
                previous_distance = float(value)
            risks = previous.get("component_risks")
            if isinstance(risks, dict):
                previous_component_risks = {
                    str(key): float(value)
                    for key, value in risks.items()
                    if isinstance(value, (int, float))
                }

        if trusted_evidence_projection is not None and verification_evidence is not None:
            raise ValueError(
                "verification_evidence_conflicts_with_trusted_evidence_projection"
            )

        binding_issues: tuple[str, ...] = ()
        if trusted_evidence_projection is not None:
            if trusted_evidence_binding is None:
                binding_issues = ("trusted_evidence_binding_required",)
            else:
                binding_issues = trusted_evidence_binding_issues(
                    trusted_evidence_projection,
                    trusted_evidence_binding,
                )
                if trusted_evidence_binding.operation_id != operation_id:
                    binding_issues = tuple(
                        sorted(
                            set(binding_issues)
                            | {"trusted_evidence_operation_id_mismatch"}
                        )
                    )

        if binding_issues:
            effective_verification = VerificationEvidence(
                factual=VerificationStatus.CONTRADICTED,
                execution=VerificationStatus.UNVERIFIED,
            )
        else:
            effective_verification = (
                trusted_evidence_projection.verification
                if trusted_evidence_projection is not None
                else verification_evidence
            )

        runtime_issues: tuple[str, ...] = ()
        runtime_projection: TrustedEvidenceProjection | None = None
        if runtime_execution_attestation is not None:
            runtime_issues = runtime_attestation_issues(
                runtime_execution_attestation,
                operation_id=operation_id,
                evaluated_at=datetime.now(UTC).isoformat(),
            )
            if (
                trusted_evidence_projection is not None
                and runtime_execution_attestation.source_digest
                != trusted_evidence_projection.source_digest
            ):
                runtime_issues = tuple(
                    sorted(
                        set(runtime_issues)
                        | {"runtime_attestation_source_digest_mismatch"}
                    )
                )
            runtime_projection = from_runtime_execution_attestation(
                runtime_execution_attestation
            )

        if runtime_projection is not None and not runtime_issues:
            base = effective_verification or VerificationEvidence()
            effective_verification = VerificationEvidence(
                factual=base.factual,
                execution=runtime_projection.verification.execution,
            )

        qualification = qualification_layer.qualify(
            rank=result.rank.value,
            risk_signals=scores,
            verification=effective_verification,
            sufficiency=sufficiency_evidence,
            previous_distance=previous_distance,
            previous_component_risks=previous_component_risks,
        )
        policy_signals = {**scores, **qualification.as_policy_signals()}

        caller_context = governance_context or GovernanceRequestContext()
        operation_policy = get_operation_policy(operation_id)
        if operation_policy is None:
            context = merge_governance_contexts(
                caller_context,
                GovernanceRequestContext(required_scopes=("__unknown_operation__",)),
            )
        else:
            context = merge_governance_contexts(
                operation_policy.as_context(),
                caller_context,
            )

        if context.required_scopes:
            granted_scopes = {
                tag.removeprefix("scope:")
                for tag in agent.tags
                if tag.startswith("scope:")
            }
            if set(context.required_scopes) - granted_scopes:
                policy_signals["authorization_failure"] = 1.0

        verification = effective_verification or VerificationEvidence()
        sufficiency = sufficiency_evidence or TaskSufficiencyEvidence()
        missing_required_evidence = (
            (
                context.require_factual_evidence
                and verification.factual != VerificationStatus.VERIFIED
            )
            or (
                context.require_execution_evidence
                and verification.execution != VerificationStatus.VERIFIED
            )
            or (
                context.require_task_sufficiency
                and sufficiency.status != SufficiencyStatus.SUFFICIENT
            )
        )
        if operation_policy is not None and operation_policy.require_runtime_attestation:
            if runtime_execution_attestation is None or runtime_issues:
                missing_required_evidence = True
        if missing_required_evidence:
            policy_signals["missing_required_evidence"] = 1.0

        decision = policy_engine.decide(
            agent=agent,
            fate_vector=fate_vector,
            rank=result.rank.value,
            reward=result.reward,
            policy=result.policy,
            repair_prompt=result.repair_prompt,
            risk_signals=policy_signals,
        )

        qualification_payload = qualification.as_dict()
        if decision.governance_gate is not None:
            qualification_payload["governance_gate"] = decision.governance_gate
            qualification_payload["governance_fail_closed"] = True
        if trusted_evidence_projection is not None:
            qualification_payload["trusted_evidence"] = {
                "source_kind": trusted_evidence_projection.source_kind,
                "source_digest": trusted_evidence_projection.source_digest,
                "binding_issues": list(binding_issues),
            }
        if runtime_execution_attestation is not None:
            qualification_payload["runtime_execution_attestation"] = {
                "operation_id": runtime_execution_attestation.operation_id,
                "actor_ref": runtime_execution_attestation.actor_ref,
                "execution_reference_id": runtime_execution_attestation.execution_reference_id,
                "attestation_digest": runtime_execution_attestation.attestation_digest,
                "succeeded": runtime_execution_attestation.succeeded,
                "issues": list(runtime_issues),
            }
        decision.qualification = qualification_payload if hasattr(decision, "qualification") else None

        decision.signature = sign_response(
            {
                "agent_id": agent_id,
                "action": decision.action.value,
                "rank": decision.rank,
                "reward": decision.reward,
                "ts": datetime.now(UTC).isoformat(),
            }
        )

        record = EvaluationRecord(
            timestamp=datetime.now(UTC).isoformat(),
            client_query=client_query,
            agent_response=agent_response,
            rank=result.rank.value,
            reward=result.reward,
            policy=result.policy,
            policy_label=decision.policy_label,
            fate_vector=fate_vector,
            repair_prompt=decision.repair_prompt,
            action_taken=decision.action,
            language=language,
            qualification=qualification_payload,
        )
        gateway_registry.add_evaluation(agent_id, record)

        if decision.agent_state != agent.state:
            gateway_registry.change_state(
                agent_id,
                decision.agent_state,
                f"Gateway policy: {decision.action.value} — {decision.message}",
            )

        lifecycle_action = lifecycle_engine.evaluate_agent(agent)
        decision.lifecycle_recommendation = lifecycle_action
        if lifecycle_action == "freeze" and agent.state == AgentState.ACTIVE:
            gateway_registry.change_state(
                agent_id,
                AgentState.FROZEN,
                f"Lifecycle: sustained low performance (avg {agent.average_reward:.2f})",
            )
        elif lifecycle_action == "escalate" and agent.state == AgentState.ACTIVE:
            gateway_registry.change_state(
                agent_id,
                AgentState.ESCALATED,
                "Lifecycle: declining performance trend",
            )
        elif lifecycle_action == "rehabilitate" and agent.state == AgentState.ACTIVE:
            gateway_registry.change_state(
                agent_id,
                AgentState.REHABILITATING,
                f"Lifecycle: low recoverable performance (avg {agent.average_reward:.2f})",
            )
        elif lifecycle_action == "upgrade":
            decision.message = f"{decision.message} Lifecycle recommendation: upgrade."

        return decision


gateway_engine = GatewayEngine()
