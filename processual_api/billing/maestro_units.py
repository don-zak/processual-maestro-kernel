from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Final

MAESTRO_UNIT_CONTRACT_VERSION: Final = "2026-08-maestro-units-v1"
MAESTRO_UNIT_METRIC: Final = "maestro_units"
LEGACY_CREDIT_ALIAS_RATIO: Final = 1


@dataclass(frozen=True, slots=True)
class MaestroUnitRule:
    path: str
    endpoint_class: str
    units: int
    capability_code: str | None = None
    free: bool = False
    variable_by_item_count: bool = False

    def __post_init__(self) -> None:
        if not self.path.startswith("/"):
            raise ValueError("Maestro unit rule path must be absolute")
        if self.units < 0:
            raise ValueError("Maestro units must not be negative")
        if self.free and self.units != 0:
            raise ValueError("free Maestro unit rules must cost zero units")
        if self.variable_by_item_count and self.units <= 0:
            raise ValueError("variable Maestro unit rules require a positive base unit cost")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


_FREE_RULES = {
    "/health/live": MaestroUnitRule("/health/live", "free_operational_check", 0, free=True),
    "/health/ready": MaestroUnitRule("/health/ready", "free_operational_check", 0, free=True),
    "/adapters/status": MaestroUnitRule("/adapters/status", "free_operational_check", 0, free=True),
    "/cgt/govern/status": MaestroUnitRule("/cgt/govern/status", "free_operational_check", 0, free=True),
    "/settings/subscription": MaestroUnitRule("/settings/subscription", "free_operational_check", 0, free=True),
}

_METERED_RULES = {
    "/cgt/analyze": MaestroUnitRule(
        "/cgt/analyze", "analysis_evaluation", 1, capability_code="maestro_execution"
    ),
    "/cgt/govern": MaestroUnitRule(
        "/cgt/govern", "governance_evaluation", 1, capability_code="maestro_execution"
    ),
    "/cgt/govern/batch": MaestroUnitRule(
        "/cgt/govern/batch",
        "batch_governance_evaluation",
        1,
        capability_code="maestro_execution",
        variable_by_item_count=True,
    ),
    "/cgt/govern/compare": MaestroUnitRule(
        "/cgt/govern/compare",
        "governance_evaluation",
        2,
        capability_code="enterprise_governance",
    ),
    "/cgt/govern/report": MaestroUnitRule(
        "/cgt/govern/report",
        "governance_evaluation",
        3,
        capability_code="enterprise_governance",
    ),
    "/cgt/govern/auto-repair": MaestroUnitRule(
        "/cgt/govern/auto-repair",
        "governance_evaluation",
        5,
        capability_code="enterprise_governance",
    ),
    "/reports/fate": MaestroUnitRule(
        "/reports/fate", "report_generation", 2, capability_code="maestro_execution"
    ),
    "/reports/generate-llm": MaestroUnitRule(
        "/reports/generate-llm",
        "report_generation",
        5,
        capability_code="maestro_execution",
    ),
}

MAESTRO_UNIT_RULES: Final = MappingProxyType({**_FREE_RULES, **_METERED_RULES})


def normalize_maestro_endpoint(endpoint: str) -> str:
    path = str(endpoint or "/").split("?", 1)[0].strip() or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return path


def maestro_unit_rule(endpoint: str) -> MaestroUnitRule | None:
    return MAESTRO_UNIT_RULES.get(normalize_maestro_endpoint(endpoint))


def maestro_units_for_endpoint(endpoint: str, item_count: int | None = None) -> int:
    rule = maestro_unit_rule(endpoint)
    if rule is None:
        return 1
    if rule.variable_by_item_count:
        return max(int(item_count or 1), 1) * rule.units
    return rule.units


def maestro_endpoint_class(endpoint: str) -> str:
    path = normalize_maestro_endpoint(endpoint)
    rule = maestro_unit_rule(path)
    if rule is not None:
        return rule.endpoint_class
    if path.startswith("/reports/"):
        return "report_generation"
    if path.startswith("/cgt/govern"):
        return "governance_evaluation"
    if path.startswith("/cgt/analyze"):
        return "analysis_evaluation"
    return "metered_api_request"


def maestro_capability_for_endpoint(endpoint: str) -> str | None:
    rule = maestro_unit_rule(endpoint)
    return None if rule is None else rule.capability_code


def is_maestro_metered_endpoint(endpoint: str) -> bool:
    rule = maestro_unit_rule(endpoint)
    return bool(rule is not None and not rule.free and rule.units > 0)


def credits_from_maestro_units(units: int) -> int:
    """Compatibility alias only; Maestro Units remain the consumption authority."""
    if units < 0:
        raise ValueError("Maestro units must not be negative")
    return units * LEGACY_CREDIT_ALIAS_RATIO


__all__ = [
    "LEGACY_CREDIT_ALIAS_RATIO",
    "MAESTRO_UNIT_CONTRACT_VERSION",
    "MAESTRO_UNIT_METRIC",
    "MAESTRO_UNIT_RULES",
    "MaestroUnitRule",
    "credits_from_maestro_units",
    "is_maestro_metered_endpoint",
    "maestro_capability_for_endpoint",
    "maestro_endpoint_class",
    "maestro_unit_rule",
    "maestro_units_for_endpoint",
    "normalize_maestro_endpoint",
]
