"""PostgreSQL-backed prepared authority for standalone External Evaluation."""

from __future__ import annotations

from typing import Any

from processual_api.services.evaluation_authority_postgres import (
    EvaluationAuthorityError,
    load_evaluation_authority_state,
    save_evaluation_authority_state,
)


async def load_prepared_evaluation_authority(owner_id: str) -> dict[str, Any]:
    """Load the shared Evaluation authority, initializing an empty snapshot if absent."""

    try:
        return await load_evaluation_authority_state(owner_id)
    except EvaluationAuthorityError as exc:
        if str(exc) == "evaluation_authority_state_missing":
            return {}
        raise


async def save_prepared_evaluation_authority(
    owner_id: str,
    raw: dict[str, Any],
) -> None:
    """Persist prepared binding/proof state into the shared Evaluation authority."""

    await save_evaluation_authority_state(owner_id, raw)


__all__ = [
    "load_prepared_evaluation_authority",
    "save_prepared_evaluation_authority",
]
