"""Public-safe trusted evidence provenance contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .verification import VerificationEvidence, VerificationStatus


@dataclass(frozen=True)
class TrustedEvidenceProjection:
    source_kind: str
    source_digest: str
    verification: VerificationEvidence
    execution_authorized: bool = False
    execution_performed: bool = False
    release_commit_sha: str | None = None
    artifact_digest: str | None = None
    case_revision: str | None = None
    scope_digest: str | None = None
    observed_at: str | None = None
    expires_at: str | None = None


@dataclass(frozen=True)
class TrustedEvidenceBinding:
    operation_id: str
    release_commit_sha: str | None = None
    artifact_digest: str | None = None
    case_revision: str | None = None
    scope_digest: str | None = None
    evaluated_at: str | None = None
    consumed_source_digests: frozenset[str] = frozenset()


def _parse_aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("trusted_evidence_timestamp_must_be_timezone_aware")
    return parsed.astimezone(UTC)


def trusted_evidence_binding_issues(
    projection: TrustedEvidenceProjection,
    binding: TrustedEvidenceBinding,
) -> tuple[str, ...]:
    issues: list[str] = []
    for field_name in ("release_commit_sha", "artifact_digest", "case_revision", "scope_digest"):
        expected = getattr(binding, field_name)
        actual = getattr(projection, field_name)
        if expected is not None and actual != expected:
            issues.append(f"trusted_evidence_{field_name}_mismatch")
    if projection.source_digest in binding.consumed_source_digests:
        issues.append("trusted_evidence_replay_detected")
    if binding.evaluated_at is not None:
        evaluated = _parse_aware(binding.evaluated_at)
        if projection.observed_at is None:
            issues.append("trusted_evidence_observed_at_missing")
        else:
            try:
                observed = _parse_aware(projection.observed_at)
            except ValueError:
                issues.append("trusted_evidence_observed_at_invalid")
            else:
                if observed > evaluated:
                    issues.append("trusted_evidence_observed_in_future")
        if projection.expires_at is not None:
            try:
                expires = _parse_aware(projection.expires_at)
            except ValueError:
                issues.append("trusted_evidence_expires_at_invalid")
            else:
                if expires <= evaluated:
                    issues.append("trusted_evidence_expired")
    return tuple(sorted(set(issues)))


def execution_projection(
    *,
    source_digest: str,
    verified: bool,
    observed_at: str | None = None,
) -> TrustedEvidenceProjection:
    return TrustedEvidenceProjection(
        source_kind="public.runtime.execution",
        source_digest=source_digest,
        verification=VerificationEvidence(
            execution=(
                VerificationStatus.VERIFIED
                if verified
                else VerificationStatus.CONTRADICTED
            )
        ),
        execution_authorized=verified,
        execution_performed=verified,
        observed_at=observed_at,
    )
