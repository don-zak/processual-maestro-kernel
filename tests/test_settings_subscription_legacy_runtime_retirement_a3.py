from __future__ import annotations

from pathlib import Path

import pytest

from processual_api.routers import settings as settings_module
from processual_api.routers import (
    settings_subscription_runtime as runtime_module,
)

RUNTIME_SOURCE = Path(
    "processual_api/routers/settings_subscription_runtime.py"
).read_text(encoding="utf-8")


def test_legacy_subscription_symbols_are_removed_from_runtime_namespace() -> None:
    for legacy_name in (
        "_load_billing_subscriptions",
        "_compute_stage",
        "get_subscription",
    ):
        assert not hasattr(settings_module, legacy_name)


def test_runtime_plan_resolvers_do_not_reference_legacy_subscription_storage() -> None:
    assert "subscriptions.json" not in RUNTIME_SOURCE
    assert "_load_billing_subscriptions" in RUNTIME_SOURCE
    assert "delattr(settings_module, legacy_name)" in RUNTIME_SOURCE


def test_client_integration_plan_prefers_verified_claims() -> None:
    plan = runtime_module.resolve_client_integration_plan_without_legacy_storage(
        "ignored-user",
        {"subscription": {"plan": "starter"}},
        {"plan_id": "enterprise_integration"},
    )

    assert plan == "enterprise_integration"


def test_client_integration_plan_uses_local_authority_but_missing_plan_fails_closed() -> None:
    local_plan = runtime_module.resolve_client_integration_plan_without_legacy_storage(
        "ignored-user",
        {"subscription": {"plan_id": "business"}},
        {},
    )

    assert local_plan == "business"

    with pytest.raises(ValueError, match="authoritative subscription plan is required"):
        runtime_module.resolve_client_integration_plan_without_legacy_storage(
            "ignored-user",
            {},
            {},
        )

    with pytest.raises(ValueError, match="authoritative subscription plan is required"):
        runtime_module.resolve_current_plan_without_legacy_storage(
            "ignored-user",
            {},
        )


def test_api_key_plan_resolution_uses_installed_non_legacy_resolver() -> None:
    assert (
        settings_module._resolve_client_api_key_integration_plan_id
        is runtime_module.resolve_client_integration_plan_without_legacy_storage
    )
    assert (
        settings_module._resolve_current_plan_id
        is runtime_module.resolve_current_plan_without_legacy_storage
    )
