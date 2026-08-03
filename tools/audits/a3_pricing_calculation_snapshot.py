from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from processual_api.billing.maestro_group1_selected_pricing import (
    SELECTED_MONTHLY_PRICES,
    SELECTED_OVERAGE_PRICES_PER_1000_UNITS,
    build_selected_pricing_proposal,
)

ROOT = Path(__file__).resolve().parents[2]

REFERENCE_FILES = (
    "processual_api/billing/maestro_reference_workloads.py",
    "processual_api/billing/maestro_calibration_contracts.py",
    "processual_api/billing/maestro_shadow_measurements.py",
    "processual_api/billing/unit_cost_assumptions.py",
    "processual_api/billing/maestro_group1_pricing_review.py",
    "processual_api/billing/maestro_group1_selected_pricing.py",
    "processual_api/billing/commercial_catalog_contracts.py",
    "processual_api/billing/usage_pricing.py",
    "processual_api/billing/commercial_quota_top_up_contracts.py",
    "processual_api/billing/offer_pricebook.py",
    "processual_api/billing/subscription_catalog.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    files: list[dict[str, Any]] = []

    for relative_path in REFERENCE_FILES:
        path = ROOT / relative_path

        files.append(
            {
                "path": relative_path,
                "exists": path.exists(),
                "sha256": sha256(path) if path.exists() else None,
            }
        )

    payload = {
        "reference_type": "maestro_pricing_calculation_snapshot",
        "public_price_policy": {
            "priced_through": "enterprise_pilot",
            "post_pilot_display": "assessment_without_public_price",
        },
        "selected_monthly_prices_usd": {
            plan_id: str(price)
            for plan_id, price in SELECTED_MONTHLY_PRICES.items()
        },
        "selected_overage_prices_per_1000_units_usd": {
            plan_id: str(price)
            for plan_id, price in (
                SELECTED_OVERAGE_PRICES_PER_1000_UNITS.items()
            )
        },
        "selected_pricing_proposal": build_selected_pricing_proposal(),
        "reference_files": files,
    }

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
