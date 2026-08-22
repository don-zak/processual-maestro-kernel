from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "processual_api"
LEGACY_SERVICE = API_ROOT / "admin_marketplace" / "subscription_usage_service.py"
LEGACY_BACKFILL = (
    API_ROOT / "admin_marketplace" / "subscription_legacy_quota_cycle_backfill.py"
)
STAGING_SMOKE = API_ROOT / "staging_smoke.py"


def test_legacy_subscription_usage_runtime_files_are_deleted() -> None:
    assert not LEGACY_SERVICE.exists()
    assert not LEGACY_BACKFILL.exists()


def test_no_production_module_references_retired_legacy_usage_paths() -> None:
    offenders: list[str] = []
    retired_tokens = (
        "subscription_usage_service",
        "record_subscription_usage_factory",
        "subscription_legacy_quota_cycle_backfill",
        "backfill_legacy_quota_cycles_in_session",
        "SqlAlchemySubscriptionQuotaRepository",
        "SqlAlchemySubscriptionUsageRepository",
        "AdminMarketSubscriptionQuotaAccount",
        "AdminMarketSubscriptionUsageLedger",
    )
    for path in sorted(API_ROOT.rglob("*.py")):
        if path == STAGING_SMOKE:
            continue
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in retired_tokens):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_staging_smoke_mentions_legacy_service_only_as_a_negative_guard() -> None:
    source = STAGING_SMOKE.read_text(encoding="utf-8")

    assert 'if "record_subscription_usage_factory" in usage_source:' in source
    assert "legacy quota-account usage service is installed" in source
    assert "from processual_api.admin_marketplace.subscription_usage_service" not in source
