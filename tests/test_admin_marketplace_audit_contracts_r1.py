from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from processual_api.admin_marketplace.audit_contracts import (
    CommercialAuditAction,
    CommercialAuditOutcome,
    CommercialAuditRecord,
    CommercialResourceType,
)
from processual_api.admin_marketplace.errors import AdminMarketplaceAuditSafetyError


def _record(**updates):
    values = {
        "event_id": "event_001",
        "occurred_at": datetime.now(UTC),
        "actor_user_id": "user_001",
        "actor_session_id": "session_001",
        "platform_authority": "platform_admin",
        "action": CommercialAuditAction.OFFER_DECIDED,
        "resource_type": CommercialResourceType.OFFER,
        "resource_id": "offer_001",
        "outcome": CommercialAuditOutcome.ALLOWED,
        "reason_code": "offer_approved",
        "correlation_id": "corr_001",
        "previous_state_digest": "a" * 64,
        "new_state_digest": "b" * 64,
        "metadata": {"channel": "maestro_direct"},
    }
    values.update(updates)
    return CommercialAuditRecord(**values)


def test_commercial_audit_record_is_immutable_and_safe() -> None:
    record = _record()
    assert record.platform_authority == "platform_admin"
    with pytest.raises(FrozenInstanceError):
        record.reason_code = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        record.metadata["channel"] = "lemon_squeezy"  # type: ignore[index]


def test_audit_rejects_sensitive_metadata_and_unknown_authority() -> None:
    with pytest.raises(AdminMarketplaceAuditSafetyError, match="Sensitive"):
        _record(metadata={"api_key": "raw-secret"})
    with pytest.raises(AdminMarketplaceAuditSafetyError, match="authority"):
        _record(platform_authority="platform_supervisor")


def test_order_creation_accepts_authenticated_customer_authority() -> None:
    record = _record(
        platform_authority="identity_customer",
        action=CommercialAuditAction.ORDER_CREATED,
        resource_type=CommercialResourceType.ORDER,
    )

    assert record.platform_authority == "identity_customer"


def test_audit_requires_timezone_and_sha256_digests() -> None:
    with pytest.raises(AdminMarketplaceAuditSafetyError, match="timezone-aware"):
        _record(occurred_at=datetime.now())
    with pytest.raises(AdminMarketplaceAuditSafetyError, match="SHA-256"):
        _record(new_state_digest="not-a-digest")


def test_audit_rejects_unknown_enum_values() -> None:
    with pytest.raises(
        AdminMarketplaceAuditSafetyError,
        match="valid CommercialAuditAction",
    ):
        _record(action="unknown_action")

    with pytest.raises(
        AdminMarketplaceAuditSafetyError,
        match="valid CommercialResourceType",
    ):
        _record(resource_type="unknown_resource")

    with pytest.raises(
        AdminMarketplaceAuditSafetyError,
        match="valid CommercialAuditOutcome",
    ):
        _record(outcome="unknown_outcome")
