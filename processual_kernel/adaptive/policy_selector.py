from __future__ import annotations

from ..adaptive_types import AmbiguityLevel, PolicyName, PolicyProfile, RiskLevel, TaskDuration, TaskProfile, TaskSize
from ..types import KernelPolicy
from .policy_profiles import build_policy_profiles


class PolicySelector:
    """Maps TaskProfile to a safe policy profile."""

    def __init__(self, base_policy: KernelPolicy | None = None):
        self.base_policy = base_policy or KernelPolicy()
        self._profiles = build_policy_profiles(self.base_policy)

    def select(self, profile: TaskProfile) -> PolicyProfile:
        if profile.risk == RiskLevel.CRITICAL:
            return self._profiles[PolicyName.CRITICAL_SAFETY]
        if profile.risk == RiskLevel.HIGH:
            return self._profiles[PolicyName.CONSERVATIVE]
        if profile.metadata.get("quality_first"):
            return self._profiles[PolicyName.QUALITY_FIRST]
        if profile.budget_sensitivity in (RiskLevel.HIGH, RiskLevel.CRITICAL) or profile.metadata.get("cost_saving"):
            return self._profiles[PolicyName.COST_SAVING]
        if profile.duration == TaskDuration.LONG:
            return self._profiles[PolicyName.LONG_RUNNING]
        if profile.ambiguity == AmbiguityLevel.HIGH or profile.metadata.get("exploratory"):
            return self._profiles[PolicyName.EXPLORATORY]
        if profile.size == TaskSize.SMALL and profile.duration == TaskDuration.SHORT and profile.risk == RiskLevel.LOW:
            return self._profiles[PolicyName.FAST]
        return self._profiles[PolicyName.BALANCED]
