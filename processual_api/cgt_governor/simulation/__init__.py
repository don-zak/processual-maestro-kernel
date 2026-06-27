"""CGT Governor — Simulation Package

Supervision simulation engine that evaluates multiple virtual LLM agents
through governance pipeline and produces oversight reports.
"""

from .agents import ALL_AGENTS, AgentPersona
from .engine import SimulationEngine, SimulationResult
from .reports import generate_supervision_pdf
from .scenarios import ALL_SCENARIOS, Scenario

__all__ = [
    "ALL_AGENTS",
    "AgentPersona",
    "ALL_SCENARIOS",
    "Scenario",
    "SimulationEngine",
    "SimulationResult",
    "generate_supervision_pdf",
]
