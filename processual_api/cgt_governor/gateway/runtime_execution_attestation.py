"""Public runtime execution attestation contract."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .trusted_evidence import TrustedEvidenceProjection
from .verification import VerificationEvidence, VerificationStatus

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,239}$")


def _aware(name: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name}_must_be_iso_datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name}_must_be_timezone_aware")
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class RuntimeExecutionAttestation:
    operation_id: str
    actor_ref: str
    execution_reference_id: str
    source_digest: str
    performed_at: str
    attested_at: str
    succeeded: bool
    attestation_digest: str

    def __post_init__(self) -> None:
        for name in ("operation_id", "actor_ref", "execution_reference_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or _SAFE_ID.fullmatch(value.strip()) is None:
                raise ValueError(f"{name}_invalid")
        if _SHA256.fullmatch(self.source_digest) is None:
            raise ValueError("source_digest_must_be_sha256")
        if _SHA256.fullmatch(self.attestation_digest) is None:
            raise ValueError("attestation_digest_must_be_sha256")
        if _aware("attested_at", self.attested_at) < _aware("performed_at", self.performed_at):
            raise ValueError("attestation_cannot_predate_execution")
        if self.attestation_digest != runtime_execution_attestation_digest(self):
            raise ValueError("runtime_execution_attestation_digest_mismatch")


def runtime_execution_attestation_digest(attestation: RuntimeExecutionAttestation) -> str:
    payload = {
        "actor_ref": attestation.actor_ref.strip().lower(),
        "attested_at": _aware("attested_at", attestation.attested_at).isoformat(),
        "execution_reference_id": attestation.execution_reference_id.strip().lower(),
        "operation_id": attestation.operation_id.strip().lower(),
        "performed_at": _aware("performed_at", attestation.performed_at).isoformat(),
        "source_digest": attestation.source_digest,
        "succeeded": attestation.succeeded,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def build_runtime_execution_attestation(
    *,
    operation_id: str,
    actor_ref: str,
    execution_reference_id: str,
    source_digest: str,
    performed_at: str,
    attested_at: str,
    succeeded: bool,
) -> RuntimeExecutionAttestation:
    provisional = object.__new__(RuntimeExecutionAttestation)
    values = {
        "operation_id": operation_id,
        "actor_ref": actor_ref,
        "execution_reference_id": execution_reference_id,
        "source_digest": source_digest,
        "performed_at": performed_at,
        "attested_at": attested_at,
        "succeeded": succeeded,
        "attestation_digest": "0" * 64,
    }
    for key, value in values.items():
        object.__setattr__(provisional, key, value)
    values["attestation_digest"] = runtime_execution_attestation_digest(provisional)
    return RuntimeExecutionAttestation(**values)


def runtime_attestation_issues(
    attestation: RuntimeExecutionAttestation,
    *,
    operation_id: str,
    evaluated_at: str,
) -> tuple[str, ...]:
    issues: list[str] = []
    evaluated = _aware("evaluated_at", evaluated_at)
    if attestation.operation_id != operation_id:
        issues.append("runtime_attestation_operation_mismatch")
    if _aware("performed_at", attestation.performed_at) > evaluated:
        issues.append("runtime_attestation_execution_from_future")
    if _aware("attested_at", attestation.attested_at) > evaluated:
        issues.append("runtime_attestation_attested_from_future")
    if not attestation.succeeded:
        issues.append("runtime_attestation_execution_failed")
    return tuple(sorted(set(issues)))


def from_runtime_execution_attestation(
    attestation: RuntimeExecutionAttestation,
) -> TrustedEvidenceProjection:
    return TrustedEvidenceProjection(
        source_kind="public.runtime.execution_attestation",
        source_digest=attestation.attestation_digest,
        verification=VerificationEvidence(
            execution=(
                VerificationStatus.VERIFIED
                if attestation.succeeded
                else VerificationStatus.CONTRADICTED
            )
        ),
        execution_authorized=attestation.succeeded,
        execution_performed=attestation.succeeded,
        observed_at=attestation.attested_at,
    )
