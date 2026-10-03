"""Fail-closed public orchestration seam for PRIVATE, admission-qualified CGT.

The public SDK knows neither the private evidence nor Fate Vector equations.
A deployed server must inject a trusted private admission backend AND a
private evaluator that independently verifies the same signed evidence pair.
This file cannot make a customer-supplied receipt authoritative.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .admission_port import (
    GovernanceEvidenceUnavailable, SafeAdmissionReceipt, TrustedAdmissionPort,
    require_admitted,
)

T = TypeVar("T")


class AdmissionFirstGovernanceExecution:
    """Invokes the private core only after trusted private data admission."""

    def __init__(self, *, private_backend: TrustedAdmissionPort | None,
                 private_evaluator: Callable[..., T] | None):
        self.private_backend = private_backend
        self.private_evaluator = private_evaluator

    def evaluate(self, *, entity_type: str, entity_id: str,
                 operational: bool = False) -> T:
        # Never accept raw telemetry, fake signed envelopes, or a safe
        # receipt supplied by the client as the proof of qualification.
        if self.private_evaluator is None:
            raise GovernanceEvidenceUnavailable("private_core_unavailable")
        require_admitted(self.private_backend, entity_type=entity_type,
                         entity_id=entity_id, operational=operational)
        try:
            return self.private_evaluator(
                entity_type=entity_type, entity_id=entity_id,
                operational=operational)
        except Exception:
            # This boundary must not surface private core internals or secrets.
            raise GovernanceEvidenceUnavailable("private_qualified_evaluation_failed") from None
