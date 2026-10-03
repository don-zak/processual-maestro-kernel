"""Public, intentionally content-free admission integration contract.

This is NOT a verifier and confers no authority. A trusted PRIVATE backend must
implement the port, validate the original measurements and attestation, and
return a sanitized receipt. The public distribution must not ship HMAC keys,
private CGT weights, signed source traces, or a fallback that grants access.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class GovernanceEvidenceUnavailable(RuntimeError):
    """No trustworthy evidence admission; no governance calculation permitted."""


@dataclass(frozen=True, slots=True)
class SafeAdmissionReceipt:
    entity_type: str
    entity_id: str
    evidence_sha256: str
    calibration_version: str
    schema_version: str
    data_admissible: bool
    operational_fate_allowed: bool
    reason_codes: tuple[str, ...] = ()


@runtime_checkable
class TrustedAdmissionPort(Protocol):
    def require_admitted(self, *, entity_type: str, entity_id: str,
                         operational: bool = False) -> SafeAdmissionReceipt:
        """MUST be implemented by server-side trusted/private admission."""


def require_admitted(port: TrustedAdmissionPort | None, *,
                     entity_type: str, entity_id: str,
                     operational: bool = False) -> SafeAdmissionReceipt:
    """Validate a trusted port's SAFE receipt without exposing private data.

    A receipt alone must never be accepted from a customer request or used
    to grant production authority; the backend behind 'port' is authoritative.
    """
    if port is None or not isinstance(port, TrustedAdmissionPort):
        raise GovernanceEvidenceUnavailable("trusted_admission_backend_unavailable")
    try:
        receipt = port.require_admitted(
            entity_type=entity_type, entity_id=entity_id, operational=operational)
    except Exception as exc:
        raise GovernanceEvidenceUnavailable("trusted_evidence_rejected") from None
    if not isinstance(receipt, SafeAdmissionReceipt):
        raise GovernanceEvidenceUnavailable("invalid_admission_receipt")
    if receipt.entity_type != entity_type or receipt.entity_id != entity_id:
        raise GovernanceEvidenceUnavailable("admission_subject_mismatch")
    if (not receipt.data_admissible or len(receipt.evidence_sha256) != 64
            or any(ch not in "0123456789abcdef" for ch in receipt.evidence_sha256)):
        raise GovernanceEvidenceUnavailable("insufficient_evidence")
    if operational and not receipt.operational_fate_allowed:
        raise GovernanceEvidenceUnavailable("operational_calibration_not_approved")
    return receipt
