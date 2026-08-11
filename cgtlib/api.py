from __future__ import annotations

from ._stable_api import CGTLIB_STABLE_API as CGTLIB_STABLE_API
from .reference_data import (
    ReferenceScenarioRecord,
)
from .types import (
    AftermathState,
    CompatibilityState,
    GateState,
    LockState,
    NodeState,
)


def build_public_api_snapshot() -> dict[str, object]:
    return {
        "library": "cgtlib",
        "surface": "stable-api",
        "symbol_count": len(CGTLIB_STABLE_API),
        "symbols": list(CGTLIB_STABLE_API),
    }


__all__ = list(CGTLIB_STABLE_API) + [
    "AftermathState",
    "CompatibilityState",
    "GateState",
    "LockState",
    "NodeState",
    "ReferenceScenarioRecord",
    "build_public_api_snapshot",
]
