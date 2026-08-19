"""CGT Governor — Simulation Package.

The public simulation boundary remains importable without optional PDF/reporting
packages. Report generation is loaded only when explicitly requested.
"""

from __future__ import annotations

from typing import Any

from .agents import ALL_AGENTS, AgentPersona
from .engine import SimulationEngine, SimulationResult
from .scenarios import ALL_SCENARIOS, Scenario


def generate_supervision_pdf(*args: Any, **kwargs: Any) -> Any:
    """Load the optional reporting stack only for explicit PDF generation."""
    from .reports import generate_supervision_pdf as _generate_supervision_pdf

    return _generate_supervision_pdf(*args, **kwargs)


__all__ = [
    "ALL_AGENTS",
    "AgentPersona",
    "ALL_SCENARIOS",
    "Scenario",
    "SimulationEngine",
    "SimulationResult",
    "generate_supervision_pdf",
]
