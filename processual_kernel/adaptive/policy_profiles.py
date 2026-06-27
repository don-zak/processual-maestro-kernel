from __future__ import annotations

from dataclasses import replace

from ..adaptive_types import PolicyName, PolicyProfile, RuntimeMode
from ..types import KernelPolicy


def _policy(base: KernelPolicy, version: str, **overrides) -> KernelPolicy:
    return replace(base, policy_version=version, **overrides)


def build_policy_profiles(base_policy: KernelPolicy | None = None) -> dict[PolicyName, PolicyProfile]:
    base = base_policy or KernelPolicy()
    return {
        PolicyName.FAST: PolicyProfile(
            name=PolicyName.FAST,
            policy_version="fast-1.0.0",
            kernel_policy=_policy(base, "fast-1.0.0", max_step_attempts=1),
            checkpoint_interval_minutes=None,
            runtime_mode=RuntimeMode.OBSERVE,
            max_agents=2,
            max_retries=1,
            parallel_execution=False,
            drift_sensitivity=0.45,
            min_sample_size=20,
            notes=("short low-risk workflows",),
        ),
        PolicyName.BALANCED: PolicyProfile(
            name=PolicyName.BALANCED,
            policy_version="balanced-1.0.0",
            kernel_policy=_policy(base, "balanced-1.0.0"),
            checkpoint_interval_minutes=30,
            runtime_mode=RuntimeMode.RECOMMEND,
            max_agents=4,
            max_retries=base.max_step_attempts,
            parallel_execution=True,
            drift_sensitivity=0.35,
            min_sample_size=20,
            notes=("default policy profile",),
        ),
        PolicyName.CONSERVATIVE: PolicyProfile(
            name=PolicyName.CONSERVATIVE,
            policy_version="conservative-1.0.0",
            kernel_policy=_policy(
                base,
                "conservative-1.0.0",
                quarantine_policy_risk=min(base.quarantine_policy_risk, 0.78),
                min_edge_psi=max(base.min_edge_psi, 0.0),
                min_workflow_psi=max(base.min_workflow_psi, 0.02),
                max_step_attempts=1,
                critical_requires_review=True,
            ),
            checkpoint_interval_minutes=30,
            runtime_mode=RuntimeMode.RECOMMEND,
            max_agents=3,
            max_retries=1,
            parallel_execution=False,
            drift_sensitivity=0.25,
            min_sample_size=30,
            human_gate_required=True,
            notes=("sensitive workflows", "human review for risky changes"),
        ),
        PolicyName.LONG_RUNNING: PolicyProfile(
            name=PolicyName.LONG_RUNNING,
            policy_version="long-running-1.0.0",
            kernel_policy=_policy(base, "long-running-1.0.0", max_step_attempts=2),
            checkpoint_interval_minutes=60,
            runtime_mode=RuntimeMode.RECOMMEND,
            max_agents=6,
            max_retries=2,
            parallel_execution=True,
            drift_sensitivity=0.30,
            min_sample_size=30,
            notes=("hourly checkpoint", "event-based checkpoint on risk"),
        ),
        PolicyName.QUALITY_FIRST: PolicyProfile(
            name=PolicyName.QUALITY_FIRST,
            policy_version="quality-first-1.0.0",
            kernel_policy=_policy(base, "quality-first-1.0.0", max_step_attempts=3, min_edge_psi=0.0),
            checkpoint_interval_minutes=30,
            runtime_mode=RuntimeMode.RECOMMEND,
            max_agents=6,
            max_retries=3,
            parallel_execution=True,
            drift_sensitivity=0.25,
            min_sample_size=25,
            notes=("quality over cost",),
        ),
        PolicyName.COST_SAVING: PolicyProfile(
            name=PolicyName.COST_SAVING,
            policy_version="cost-saving-1.0.0",
            kernel_policy=_policy(base, "cost-saving-1.0.0", max_step_attempts=1),
            checkpoint_interval_minutes=30,
            runtime_mode=RuntimeMode.RECOMMEND,
            max_agents=2,
            max_retries=1,
            parallel_execution=False,
            drift_sensitivity=0.40,
            min_sample_size=30,
            notes=("minimize retry and agent bloat",),
        ),
        PolicyName.EXPLORATORY: PolicyProfile(
            name=PolicyName.EXPLORATORY,
            policy_version="exploratory-1.0.0",
            kernel_policy=_policy(base, "exploratory-1.0.0", max_step_attempts=2),
            checkpoint_interval_minutes=30,
            runtime_mode=RuntimeMode.OBSERVE,
            max_agents=8,
            max_retries=2,
            parallel_execution=True,
            drift_sensitivity=0.45,
            min_sample_size=40,
            notes=("shadow learning only",),
        ),
        PolicyName.CRITICAL_SAFETY: PolicyProfile(
            name=PolicyName.CRITICAL_SAFETY,
            policy_version="critical-safety-1.0.0",
            kernel_policy=_policy(
                base,
                "critical-safety-1.0.0",
                quarantine_policy_risk=min(base.quarantine_policy_risk, 0.65),
                min_edge_psi=max(base.min_edge_psi, 0.05),
                min_workflow_psi=max(base.min_workflow_psi, 0.05),
                max_step_attempts=1,
                critical_requires_review=True,
            ),
            checkpoint_interval_minutes=30,
            runtime_mode=RuntimeMode.RESTRICTED_CRITICAL,
            max_agents=3,
            max_retries=1,
            parallel_execution=False,
            drift_sensitivity=0.20,
            min_sample_size=50,
            human_gate_required=True,
            notes=("no automatic critical adaptation", "human gate preserved"),
        ),
    }


def get_policy_profile(name: PolicyName | str, base_policy: KernelPolicy | None = None) -> PolicyProfile:
    if isinstance(name, str):
        name = PolicyName(name)
    return build_policy_profiles(base_policy)[name]
