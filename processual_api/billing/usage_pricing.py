from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final

from processual_api.billing.maestro_units import (
    MAESTRO_UNIT_METRIC,
    MAESTRO_UNIT_RULES,
    maestro_endpoint_class,
    maestro_units_for_endpoint,
    normalize_maestro_endpoint,
)
from processual_api.billing.plan_capability_matrix import plan_can_execute
from