from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from ..adaptive_types import DecisionOutcome


@dataclass(slots=True)
class DecisionLedgerEntry:
    decision_id: str
    workflow_id: str | None
    action: str
    policy_version: str
    important: bool = True
    outcome: DecisionOutcome | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    outcome_recorded_at: float | None = None


class DecisionLedger:
    """Tracks important decisions until an outcome score is attached.

    The ledger is intentionally external to the kernel. It provides safety/accountability coverage without changing
    the core Ψ equations or cgtlib evaluation path.
    """

    def __init__(self):
        self.entries: dict[str, DecisionLedgerEntry] = {}

    def record(
        self, decision, workflow_id: str | None = None, important: bool = True, **metadata: Any
    ) -> DecisionLedgerEntry:
        decision_id = getattr(decision, "decision_id")
        action = getattr(getattr(decision, "action", None), "value", None) or getattr(
            getattr(decision, "new_state", None), "value", "unknown"
        )
        entry = DecisionLedgerEntry(
            decision_id=decision_id,
            workflow_id=workflow_id or getattr(decision, "workflow_id", None),
            action=str(action),
            policy_version=str(getattr(decision, "policy_version", "unversioned")),
            important=important,
            metadata=dict(metadata),
        )
        self.entries[decision_id] = entry
        return entry

    def attach_outcome(self, outcome: DecisionOutcome) -> DecisionLedgerEntry | None:
        entry = self.entries.get(outcome.decision_id)
        if entry is None:
            return None
        entry.outcome = outcome
        entry.outcome_recorded_at = time.time()
        return entry

    def pending(self, important_only: bool = True) -> tuple[DecisionLedgerEntry, ...]:
        return tuple(
            entry
            for entry in self.entries.values()
            if entry.outcome is None and (entry.important or not important_only)
        )

    def coverage_ratio(self, important_only: bool = True) -> float:
        entries = [entry for entry in self.entries.values() if entry.important or not important_only]
        if not entries:
            return 1.0
        covered = sum(1 for entry in entries if entry.outcome is not None)
        return round(covered / len(entries), 4)
