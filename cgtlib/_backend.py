"""Resolve the optional private CGT engine for public cgtlib modules.

Public distributions intentionally do not ship ``cgtlib.private``.  All public
wrappers must resolve the engine through this module so importing the public
package remains safe and unavailable private-only operations fail closed via
``cgtlib._fallback``.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from . import _fallback

try:
    from cgtlib.private import compute as compute
except ModuleNotFoundError as exc:
    if exc.name not in {"cgtlib.private", "cgtlib.private.compute"}:
        raise
    compute = _fallback
    HAS_PRIVATE_COMPUTE = False
else:
    HAS_PRIVATE_COMPUTE = True


def require_private_module(module_name: str, feature: str) -> ModuleType:
    """Return a private engine module or fail closed in public builds."""

    if not HAS_PRIVATE_COMPUTE:
        raise _fallback._FeatureUnavailableError(feature)
    return importlib.import_module(f"cgtlib.private.{module_name}")
