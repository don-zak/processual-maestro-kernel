"""Typed request-time governance requirements for the public gateway."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceRequestContext:
    required_scopes: tuple[str, ...] = ()
    require_factual_evidence: bool = False
    require_execution_evidence: bool = False
    require_task_sufficiency: bool = False
