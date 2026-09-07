"""Canonical External Evaluation API-key quota policy.

CRM is the baseline evaluation access class. Integration access is deliberately
more generous, but remains bounded and non-production. Keep the relationship as
an invariant instead of duplicating unrelated numeric literals across routers.
"""

from __future__ import annotations

CRM_EVALUATION_KEY_QUOTA = 100
INTEGRATION_EVALUATION_KEY_QUOTA_MULTIPLIER = 2
INTEGRATION_EVALUATION_KEY_QUOTA = (
    CRM_EVALUATION_KEY_QUOTA * INTEGRATION_EVALUATION_KEY_QUOTA_MULTIPLIER
)

EVALUATION_KEY_TYPE_CRM = "crm"
EVALUATION_KEY_TYPE_STANDARD = "standard"  # backwards-compatible alias for CRM
EVALUATION_KEY_TYPE_INTEGRATION = "integration"


def normalized_evaluation_key_type(
    requested_type: str | None,
    *,
    allowed_binding_ids: list[str] | None = None,
    allowed_endpoints: list[object] | None = None,
) -> str:
    """Resolve evaluation key class, failing safely to the CRM baseline.

    Integration runtime execution is also inferred from prepared bindings or the
    canonical task-execute endpoint, so older Admin UI payloads cannot
    accidentally receive the smaller CRM quota when they request Integration
    execution.
    """

    requested = str(requested_type or "").strip().lower()
    if requested == EVALUATION_KEY_TYPE_INTEGRATION:
        return EVALUATION_KEY_TYPE_INTEGRATION
    if allowed_binding_ids:
        return EVALUATION_KEY_TYPE_INTEGRATION
    for endpoint in allowed_endpoints or []:
        if isinstance(endpoint, dict):
            method = str(endpoint.get("method") or "").strip().upper()
            path = str(endpoint.get("path") or "").strip()
        else:
            method = str(getattr(endpoint, "method", "") or "").strip().upper()
            path = str(getattr(endpoint, "path", "") or "").strip()
        if method == "POST" and path == "/evaluation/runtime/task-execute":
            return EVALUATION_KEY_TYPE_INTEGRATION
    return EVALUATION_KEY_TYPE_CRM


def evaluation_key_quota(key_type: str) -> int:
    normalized = str(key_type or "").strip().lower()
    if normalized == EVALUATION_KEY_TYPE_INTEGRATION:
        return INTEGRATION_EVALUATION_KEY_QUOTA
    return CRM_EVALUATION_KEY_QUOTA


__all__ = [
    "CRM_EVALUATION_KEY_QUOTA",
    "EVALUATION_KEY_TYPE_CRM",
    "EVALUATION_KEY_TYPE_INTEGRATION",
    "EVALUATION_KEY_TYPE_STANDARD",
    "INTEGRATION_EVALUATION_KEY_QUOTA",
    "INTEGRATION_EVALUATION_KEY_QUOTA_MULTIPLIER",
    "evaluation_key_quota",
    "normalized_evaluation_key_type",
]
