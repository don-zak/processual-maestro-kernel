"""Authoritative calibration profiles for public agent-governance orchestration.

The public repository owns only bounded calibration metadata and thresholds.  It
never falls back to an arbitrary profile when the requested profile is unknown,
unapproved, or internally inconsistent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class CalibrationProfileError(RuntimeError):
    """Raised when an authoritative calibration profile cannot be used safely."""


@dataclass(frozen=True, slots=True)
class CalibrationProfile:
    profile_id: str
    profile_version: str
    policy_version: str
    parameters: tuple[tuple[str, float], ...]
    parameters_hash: str
    created_by: str
    approved_by: str
    reason: str
    status: str


def _parameters_hash(parameters: tuple[tuple[str, float], ...]) -> str:
    encoded = json.dumps(dict(parameters), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _profile(
    profile_id: str,
    profile_version: str,
    policy_version: str,
    parameters: tuple[tuple[str, float], ...],
    *,
    reason: str,
) -> CalibrationProfile:
    return CalibrationProfile(
        profile_id=profile_id,
        profile_version=profile_version,
        policy_version=policy_version,
        parameters=parameters,
        parameters_hash=_parameters_hash(parameters),
        created_by="system",
        approved_by="platform-admin",
        reason=reason,
        status="approved",
    )


_PROFILES: dict[str, CalibrationProfile] = {
    "default": _profile(
        "default",
        "calibration/default/v1",
        "agent-governance-policy/v1",
        (("escalation_threshold", 0.70), ("repair_threshold", 0.45), ("proof_window", 3.0)),
        reason="baseline qualification profile",
    ),
    "conservative": _profile(
        "conservative",
        "calibration/conservative/v1",
        "agent-governance-policy/v1",
        (("escalation_threshold", 0.55), ("repair_threshold", 0.35), ("proof_window", 5.0)),
        reason="restricted or elevated-risk execution",
    ),
    "permissive": _profile(
        "permissive",
        "calibration/permissive/v1",
        "agent-governance-policy/v1",
        (("escalation_threshold", 0.82), ("repair_threshold", 0.60), ("proof_window", 2.0)),
        reason="approved low-risk qualification profile",
    ),
}


def load_calibration_profile(profile_id: str) -> CalibrationProfile:
    """Return exactly the requested approved profile; never silently fall back."""

    profile = _PROFILES.get(profile_id)
    if profile is None:
        raise CalibrationProfileError("unknown_calibration_profile")
    if profile.status != "approved" or not profile.approved_by:
        raise CalibrationProfileError("unapproved_calibration_profile")
    if profile.parameters_hash != _parameters_hash(profile.parameters):
        raise CalibrationProfileError("calibration_profile_hash_mismatch")
    return profile
