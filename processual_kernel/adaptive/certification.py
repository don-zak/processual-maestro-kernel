from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from ..adaptive_types import (
    AdaptiveCertificationReport,
    AdaptiveEvidencePack,
    AdaptiveIntegrityReport,
    CertificationLevel,
    RuntimeMode,
)
from .contracts import AdaptiveOperatingContractManager


def _safe_dict(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_safe_dict(item) for item in value]
    if isinstance(value, list):
        return [_safe_dict(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _safe_dict(v) for k, v in value.items()}
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_safe_dict(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _get(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


class AdaptiveCertificationAuthority:
    """Read-only certification and integrity checks for adaptive evidence.

    The certifier does not mutate kernel state or policy state. It produces auditable reports that summarize whether
    the collected adaptive evidence is complete enough for recommend/controlled operation.
    """

    def __init__(self, contract_manager: AdaptiveOperatingContractManager | None = None):
        self.contract_manager = contract_manager or AdaptiveOperatingContractManager()

    def integrity_report(
        self, pack: AdaptiveEvidencePack, expected_checksum: str | None = None
    ) -> AdaptiveIntegrityReport:
        evidence_checksum = checksum(pack)
        validation = self.contract_manager.validate_evidence_pack(pack)
        warnings = list(validation.warnings)
        valid = validation.valid
        if expected_checksum is not None and expected_checksum != evidence_checksum:
            valid = False
            warnings.append("evidence checksum does not match expected checksum")
        return AdaptiveIntegrityReport(
            workflow_id=pack.workflow_id,
            schema_version=pack.schema_version,
            valid=valid,
            checksum=evidence_checksum,
            expected_checksum=expected_checksum,
            artifact_count=len(pack.artifacts or {}),
            count_mismatches=validation.count_mismatches,
            missing_artifacts=validation.missing_artifacts,
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def certify(self, pack: AdaptiveEvidencePack, expected_checksum: str | None = None) -> AdaptiveCertificationReport:
        integrity = self.integrity_report(pack, expected_checksum=expected_checksum)
        artifacts = pack.artifacts or {}
        quality_gate = artifacts.get("quality_gate")
        runtime_invariants = artifacts.get("runtime_invariants")
        contract_validation = artifacts.get("contract_validation")
        convergence = artifacts.get("convergence_report")
        policy = artifacts.get("policy") or {}

        q_passed = bool(_get(quality_gate, "passed", False))
        invariants_passed = bool(_get(runtime_invariants, "passed", False))
        contract_passed = bool(_get(contract_validation, "passed", False))
        convergence_stable = bool(_get(convergence, "stable", False))
        pending_outcomes = int(_get(quality_gate, "pending_outcome_count", 0) or 0)
        pending_approvals = int(_get(quality_gate, "pending_approval_count", pack.counts.get("approvals", 0)) or 0)
        runtime_mode = _get(policy, "runtime_mode", None)

        violations: list[str] = []
        warnings: list[str] = []
        if not integrity.valid:
            violations.append("evidence pack failed integrity validation")
            violations.extend(integrity.missing_artifacts)
            violations.extend(integrity.count_mismatches)
        if not q_passed:
            violations.append("quality gate has not passed")
        if not invariants_passed:
            violations.append("runtime invariants have not passed")
        if not contract_passed:
            violations.append("operating contract validation has not passed")
        if pending_outcomes:
            violations.append(f"{pending_outcomes} pending outcome(s) remain unresolved")
        if pending_approvals:
            violations.append(f"{pending_approvals} pending approval request(s) remain unresolved")
        if not convergence_stable:
            warnings.append("adaptive convergence window is not stable yet; keep expansion cautious")

        if violations:
            level = CertificationLevel.BLOCKED
            certified = False
            reason = "certification blocked by safety evidence"
        elif runtime_mode == RuntimeMode.RESTRICTED_CRITICAL.value:
            level = CertificationLevel.RESTRICTED_CRITICAL_READY
            certified = True
            reason = "restricted critical operation is evidence-backed"
        elif convergence_stable and _get(quality_gate, "eligible_next_mode") == RuntimeMode.CONTROLLED_ADAPTIVE.value:
            level = CertificationLevel.CONTROLLED_READY
            certified = True
            reason = "controlled adaptive readiness is evidence-backed"
        elif q_passed and invariants_passed and contract_passed:
            level = CertificationLevel.RECOMMEND_READY
            certified = True
            reason = "recommend-mode readiness is evidence-backed"
        else:
            level = CertificationLevel.OBSERVE_ONLY
            certified = False
            reason = "evidence supports observation only"

        return AdaptiveCertificationReport(
            workflow_id=pack.workflow_id,
            level=level,
            certified=certified,
            reason=reason,
            evidence_checksum=integrity.checksum,
            quality_gate_passed=q_passed,
            runtime_invariants_passed=invariants_passed,
            contract_validation_passed=contract_passed,
            convergence_stable=convergence_stable,
            pending_outcome_count=pending_outcomes,
            pending_approval_count=pending_approvals,
            violations=tuple(dict.fromkeys(violations)),
            warnings=tuple(dict.fromkeys(warnings + list(integrity.warnings))),
        )
