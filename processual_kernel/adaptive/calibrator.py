from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..adaptive_types import PolicyCritique, PolicyPatch, RuntimeMode
from ..types import KernelPolicy

ADJUSTABLE_FIELDS = {
    "max_step_attempts",
    "min_edge_psi",
    "min_workflow_psi",
    "quarantine_policy_risk",
    "archive_max_psi",
    "reactivation_need",
}

FORBIDDEN_FIELDS = {
    "dt",
    "alpha",
    "critical_requires_review",
    "active_min_psi",
    "min_retention",
    "max_transition_channel",
    "min_aftermath_balance",
}


class CalibrationEngine:
    """Suggests, applies, and rolls back small reversible policy changes.

    Safety invariants:
    - core Ψ/cgtlib fields are forbidden;
    - sample-size gates are enforced before suggestions and applications;
    - numeric changes must be small;
    - application is only allowed in controlled adaptive mode;
    - rollback restores the old value and bumps policy version traceably.
    """

    def __init__(self, mode: RuntimeMode = RuntimeMode.RECOMMEND, min_sample_size: int = 20):
        self.mode = mode
        self.min_sample_size = max(1, min_sample_size)
        self.patch_history: list[PolicyPatch] = []
        self.applied_patches: list[PolicyPatch] = []
        self.rollback_history: list[PolicyPatch] = []

    def suggest_patch(self, critique: PolicyCritique, min_sample_size: int | None = None) -> tuple[PolicyPatch, ...]:
        accepted: list[PolicyPatch] = []
        gate = self.min_sample_size if min_sample_size is None else max(1, min_sample_size)
        for patch in critique.suggested_changes:
            if self._is_safe(patch, gate):
                accepted.append(replace(patch, runtime_mode=self.mode))
        self.patch_history.extend(accepted)
        return tuple(accepted)

    def apply_patch(self, policy: KernelPolicy, patch: PolicyPatch, min_sample_size: int | None = None) -> KernelPolicy:
        if self.mode != RuntimeMode.CONTROLLED_ADAPTIVE:
            raise RuntimeError("patch application requires controlled adaptive mode")
        gate = self.min_sample_size if min_sample_size is None else max(1, min_sample_size)
        if not self._is_safe(patch, min_sample_size=gate):
            raise ValueError(f"unsafe or forbidden patch: {patch.field}")
        updated = replace(policy, policy_version=patch.policy_version_to, **{patch.field: patch.new_value})
        self.applied_patches.append(replace(patch, runtime_mode=self.mode))
        return updated

    def rollback_patch(self, policy: KernelPolicy, patch: PolicyPatch) -> KernelPolicy:
        if not patch.reversible:
            raise ValueError("cannot roll back irreversible patch")
        if patch.field in FORBIDDEN_FIELDS or patch.field not in ADJUSTABLE_FIELDS:
            raise ValueError(f"unsafe or forbidden rollback field: {patch.field}")
        rolled_back = replace(
            policy,
            policy_version=f"{patch.policy_version_from}+rollback",
            **{patch.field: patch.old_value},
        )
        self.rollback_history.append(replace(patch, runtime_mode=self.mode))
        return rolled_back

    @classmethod
    def _is_safe(cls, patch: PolicyPatch, min_sample_size: int) -> bool:
        if patch.field in FORBIDDEN_FIELDS or patch.field not in ADJUSTABLE_FIELDS:
            return False
        if patch.sample_size < min_sample_size:
            return False
        if not patch.reversible:
            return False
        return cls._is_small_change(patch.field, patch.old_value, patch.new_value)

    @staticmethod
    def _is_small_change(field: str, old_value: Any, new_value: Any) -> bool:
        if field == "max_step_attempts":
            return (
                isinstance(old_value, int)
                and isinstance(new_value, int)
                and abs(new_value - old_value) <= 1
                and 1 <= new_value <= 5
            )
        if isinstance(old_value, (int, float)) and isinstance(new_value, (int, float)):
            if field in {"quarantine_policy_risk", "reactivation_need"} and not (0.0 <= float(new_value) <= 1.0):
                return False
            if field in {"min_edge_psi", "min_workflow_psi", "archive_max_psi"} and not (
                -1.0 <= float(new_value) <= 1.0
            ):
                return False
            return abs(float(new_value) - float(old_value)) <= 0.15
        return old_value != new_value
