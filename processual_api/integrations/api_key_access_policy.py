"""Canonical API-key runtime access policy.

The FastAPI route registry remains authoritative for what routes exist. This
module is intentionally narrower: an endpoint is grantable only when its exact
method/path pair is declared here with a canonical task, required scopes, and
compatible operational profiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ApiKeyAccessPolicy:
    method: str
    path: str
    task_id: str
    capability: str
    operation_class: str
    required_scopes: tuple[str, ...]
    operational_profile_ids: tuple[str, ...]
    production_allowed: bool = False


def _policy(
    method: str,
    path: str,
    task_id: str,
    capability: str,
    operation_class: str,
    required_scopes: tuple[str, ...],
    operational_profile_ids: tuple[str, ...],
) -> ApiKeyAccessPolicy:
    normalized_method = method.strip().upper()
    normalized_path = path.strip()
    normalized_task = task_id.strip().lower()
    scopes = tuple(sorted({scope.strip().lower() for scope in required_scopes if scope}))
    profiles = tuple(
        sorted({profile.strip().lower() for profile in operational_profile_ids if profile})
    )
    if normalized_method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError(f"Unsupported API-key access method: {normalized_method}")
    if not normalized_path.startswith("/"):
        raise ValueError("API-key access policy paths must be absolute")
    if normalized_path.startswith(("/settings", "/admin", "/auth")):
        raise ValueError("Control-plane routes may not be API-key grantable")
    if not normalized_task.startswith("platform."):
        raise ValueError("Platform runtime task IDs must use the platform.* namespace")
    if not scopes:
        raise ValueError(f"API-key access task {normalized_task} requires at least one scope")
    if any(scope.startswith("admin:") or scope == "*" for scope in scopes):
        raise ValueError("Administrative scopes may not enter API-key runtime access policy")
    if not profiles:
        raise ValueError(f"API-key access task {normalized_task} requires an operational profile")
    return ApiKeyAccessPolicy(
        method=normalized_method,
        path=normalized_path,
        task_id=normalized_task,
        capability=capability.strip(),
        operation_class=operation_class.strip().lower(),
        required_scopes=scopes,
        operational_profile_ids=profiles,
    )


_POLICIES = {
    ("GET", "/health/live"): _policy(
        "GET",
        "/health/live",
        "platform.health.live",
        "Runtime liveness",
        "read",
        ("read:health",),
        ("platform_runtime_observability",),
    ),
    ("GET", "/health/ready"): _policy(
        "GET",
        "/health/ready",
        "platform.health.ready",
        "Runtime readiness",
        "read",
        ("read:health",),
        ("platform_runtime_observability",),
    ),
    ("GET", "/adapters/status"): _policy(
        "GET",
        "/adapters/status",
        "platform.adapters.status",
        "Adapter/provider status",
        "read",
        ("read:adapters",),
        ("platform_runtime_observability",),
    ),
    ("GET", "/cgt/govern/status"): _policy(
        "GET",
        "/cgt/govern/status",
        "platform.governor.status",
        "Governor status",
        "read",
        ("read:governor",),
        ("platform_runtime_observability", "platform_governor_sandbox"),
    ),
    ("POST", "/cgt/analyze"): _policy(
        "POST",
        "/cgt/analyze",
        "platform.cgt.analyze",
        "CGT analysis",
        "execute",
        ("run:analyze",),
        ("platform_governor_sandbox",),
    ),
    ("POST", "/cgt/govern"): _policy(
        "POST",
        "/cgt/govern",
        "platform.cgt.govern",
        "Governed evaluation",
        "execute",
        ("run:govern",),
        ("platform_governor_sandbox",),
    ),
    ("GET", "/cgt/govern/reports"): _policy(
        "GET",
        "/cgt/govern/reports",
        "platform.governor.reports",
        "Governance reports",
        "read",
        ("read:reports",),
        ("platform_runtime_observability", "platform_governor_sandbox"),
    ),
    ("POST", "/evaluation/runtime/task-execute"): _policy(
        "POST",
        "/evaluation/runtime/task-execute",
        "platform.evaluation.task_execute",
        "Bounded canonical task execution for Evaluation Runtime",
        "execute",
        ("run:evaluation",),
        ("platform_evaluation_runtime",),
    ),
}

API_KEY_ACCESS_POLICIES = MappingProxyType(_POLICIES)


def get_api_key_access_policy(method: str, path: str) -> ApiKeyAccessPolicy | None:
    return API_KEY_ACCESS_POLICIES.get((method.strip().upper(), path.strip()))


def list_api_key_access_policies() -> tuple[ApiKeyAccessPolicy, ...]:
    return tuple(API_KEY_ACCESS_POLICIES[key] for key in sorted(API_KEY_ACCESS_POLICIES))


__all__ = [
    "API_KEY_ACCESS_POLICIES",
    "ApiKeyAccessPolicy",
    "get_api_key_access_policy",
    "list_api_key_access_policies",
]
