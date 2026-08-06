from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from processual_api.billing.commercial_quota_top_up_contracts import (
    TopUpPurchaseState,
    quote_top_up,
)
from processual_api.billing.plan_fulfillment_catalog import (
    PLAN_FULFILLMENT_CATALOG_VERSION,
    QUOTA_METRIC_CODE,
    get_plan_fulfillment_spec,
)

TOP_UP_MINIMUM_MONTHLY_CONSUMPTION_PERCENT = 80


class SubscriptionTopUpEligibilityError(RuntimeError):
    """A top-up purchase cannot be authorized safely."""
