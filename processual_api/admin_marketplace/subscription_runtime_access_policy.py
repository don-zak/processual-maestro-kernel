from __future__ import annotations

from datetime import datetime


class SubscriptionRuntimeAccessError(RuntimeError):
    """Runtime access state is incomplete or inconsistent."""


def runtime_allows_usage(runtime: object, *, occurred_at: datetime) -> bool:
    if occurred_at.tzinfo is None:
        raise ValueError("runtime access timestamp must be timezone-aware.")

    stage = getattr(runtime, "access_stage", None)
    if stage == "active":
        return True
    if stage != "grace":
        return False

    grace_until = getattr(runtime, "grace_until", None)
    if grace_until is None or grace_until.tzinfo is None:
        raise SubscriptionRuntimeAccessError(
            "grace runtime requires a timezone-aware grace deadline."
        )
    return occurred_at < grace_until


def advance_expired_runtime_stage(runtime: object, *, evaluated_at: datetime) -> bool:
    if evaluated_at.tzinfo is None:
        raise ValueError("runtime evaluation timestamp must be timezone-aware.")
    if getattr(runtime, "access_stage", None) != "grace":
        return False

    grace_until = getattr(runtime, "grace_until", None)
    if grace_until is None or grace_until.tzinfo is None:
        raise SubscriptionRuntimeAccessError(
            "grace runtime requires a timezone-aware grace deadline."
        )
    if evaluated_at < grace_until:
        return False

    runtime.access_stage = "suspended"
    runtime.effective_at = grace_until
    runtime.grace_until = None
    runtime.suspended_at = grace_until
    runtime.terminated_at = None
    runtime.version += 1
    return True


__all__ = [
    "SubscriptionRuntimeAccessError",
    "advance_expired_runtime_stage",
    "runtime_allows_usage",
]
