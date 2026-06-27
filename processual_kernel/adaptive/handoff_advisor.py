from __future__ import annotations

from typing import Any

from ..adaptive_types import HandoffSchemaSuggestion, HandoffValidationResult
from ..types import HandoffTelemetry


class HandoffSchemaAdvisor:
    """Suggests and validates concrete handoff schemas when edge quality degrades."""

    def advise(
        self, edge_id: str, telemetry: HandoffTelemetry | None = None, edge_psi: float | None = None
    ) -> HandoffSchemaSuggestion:
        ambiguity = telemetry.ambiguity if telemetry is not None else 0.5
        rework = telemetry.rework_rate if telemetry is not None else 0.5
        weak = (edge_psi is not None and edge_psi < 0.0) or ambiguity >= 0.65 or rework >= 0.50
        required_fields = (
            "objective",
            "inputs_used",
            "key_findings",
            "assumptions",
            "open_questions",
            "validation_status",
            "next_agent_action",
        )
        validation_rules = (
            "objective is non-empty",
            "inputs_used lists all upstream artifacts",
            "assumptions are explicit",
            "open_questions are either empty or assigned",
            "validation_status is one of: draft, checked, blocked",
        )
        checklist = (
            "Summarize the artifact in 5 bullets or fewer",
            "Name missing context explicitly",
            "Attach confidence and known risks",
            "State the exact next action expected from the receiving agent",
        )
        return HandoffSchemaSuggestion(
            edge_id=edge_id,
            required_fields=required_fields,
            validation_rules=validation_rules,
            summary_format="objective -> evidence -> risks -> next_action",
            checklist=checklist,
            recommend_mediator=weak,
            confidence=0.82 if weak else 0.62,
            reason="handoff quality is weak or ambiguous" if weak else "schema can improve consistency",
        )

    def validate_payload(self, payload: dict[str, Any], suggestion: HandoffSchemaSuggestion) -> HandoffValidationResult:
        """Validate a proposed handoff payload against the suggested executable schema."""
        missing = tuple(
            field
            for field in suggestion.required_fields
            if field not in payload
            or payload.get(field) in (None, "")
            or (payload.get(field) == [] and field != "open_questions")
        )
        failed: list[str] = []
        validation_status = payload.get("validation_status")
        if "validation_status" in suggestion.required_fields and validation_status not in {
            "draft",
            "checked",
            "blocked",
        }:
            failed.append("validation_status must be one of: draft, checked, blocked")
        if "inputs_used" in payload and not isinstance(payload.get("inputs_used"), (list, tuple)):
            failed.append("inputs_used must list upstream artifacts")
        if "open_questions" in payload and not isinstance(payload.get("open_questions"), (list, tuple)):
            failed.append("open_questions must be a list, even when empty")
        valid = not missing and not failed
        confidence = 1.0 if valid else max(0.0, 1.0 - 0.12 * (len(missing) + len(failed)))
        return HandoffValidationResult(
            edge_id=suggestion.edge_id,
            valid=valid,
            missing_fields=missing,
            failed_rules=tuple(failed),
            confidence=round(confidence, 4),
        )
