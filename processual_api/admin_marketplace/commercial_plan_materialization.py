from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from processual_api.admin_marketplace.commercial_plan_projection import (
    CommercialPlanProjection,
    build_commercial_plan_projections,
)
from processual_api.admin_marketplace.models import AdminMarketPlan
from processual_api.billing.plan_fulfillment_catalog import PLAN_CODE_ALIASES


@dataclass(frozen=True, slots=True)
class CommercialPlanMaterializationResult:
    created: tuple[str, ...]
    updated: tuple[str, ...]
    unchanged: tuple[str, ...]
    isolated_legacy: tuple[str, ...]


def _canonical_metadata(projection: CommercialPlanProjection) -> dict[str, str]:
    return {
        **projection.metadata,
        "lifecycle_state": "canonical",
    }


def _apply_projection(row: AdminMarketPlan, projection: CommercialPlanProjection) -> bool:
    expected_metadata = _canonical_metadata(projection)
    changed = False

    for field_name, expected in (
        ("display_name", projection.display_name),
        ("entitlement_profile_ref", projection.entitlement_profile_ref),
        ("quota_profile_ref", projection.quota_profile_ref),
    ):
        if getattr(row, field_name) != expected:
            setattr(row, field_name, expected)
            changed = True

    if dict(row.metadata_json or {}) != expected_metadata:
        row.metadata_json = expected_metadata
        changed = True

    return changed


def _isolate_legacy(row: AdminMarketPlan) -> bool:
    replacement = PLAN_CODE_ALIASES.get(row.plan_code.strip().lower())
    if replacement is None:
        return False

    metadata = dict(row.metadata_json or {})
    expected = {
        **metadata,
        "lifecycle_state": "legacy_isolated",
        "replacement_plan_code": replacement,
        "commercial_authority": "compatibility_only",
    }
    if metadata == expected:
        return False
    row.metadata_json = expected
    return True


async def materialize_commercial_plans_in_session(
    session: AsyncSession,
) -> CommercialPlanMaterializationResult:
    """Reconcile plan persistence with canonical commercial projections.

    The caller owns commit/rollback. Historical legacy rows are never deleted or
    renamed here because subscriptions and orders may still reference them.
    """

    result = await session.scalars(select(AdminMarketPlan))
    existing_rows = tuple(result.all())
    by_code = {row.plan_code.strip().lower(): row for row in existing_rows}

    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    isolated_legacy: list[str] = []

    for projection in build_commercial_plan_projections():
        row = by_code.get(projection.plan_code)
        if row is None:
            row = AdminMarketPlan(
                id=uuid.uuid4(),
                plan_code=projection.plan_code,
                display_name=projection.display_name,
                entitlement_profile_ref=projection.entitlement_profile_ref,
                quota_profile_ref=projection.quota_profile_ref,
                metadata_json=_canonical_metadata(projection),
            )
            session.add(row)
            by_code[projection.plan_code] = row
            created.append(projection.plan_code)
            continue

        if _apply_projection(row, projection):
            updated.append(projection.plan_code)
        else:
            unchanged.append(projection.plan_code)

    for legacy_code in PLAN_CODE_ALIASES:
        row = by_code.get(legacy_code)
        if row is not None and _isolate_legacy(row):
            isolated_legacy.append(legacy_code)

    return CommercialPlanMaterializationResult(
        created=tuple(created),
        updated=tuple(updated),
        unchanged=tuple(unchanged),
        isolated_legacy=tuple(isolated_legacy),
    )


__all__ = [
    "CommercialPlanMaterializationResult",
    "materialize_commercial_plans_in_session",
]
