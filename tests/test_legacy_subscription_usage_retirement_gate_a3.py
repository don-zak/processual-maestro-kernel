from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "processual_api"
_ALLOWED_LEGACY_SOURCE = {
    API_ROOT / "admin_marketplace" / "subscription_usage_service.py",
    API_ROOT / "staging_smoke.py",
}


def test_no_production_module_imports_legacy_subscription_usage_service() -> None:
    offenders: list[str] = []
    for path in sorted(API_ROOT.rglob("*.py")):
        if path in _ALLOWED_LEGACY_SOURCE:
            continue
        source = path.read_text(encoding="utf-8")
        if (
            "subscription_usage_service" in source
            or "record_subscription_usage_factory" in source
        ):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_staging_smoke_mentions_legacy_service_only_as_a_negative_guard() -> None:
    source = (API_ROOT / "staging_smoke.py").read_text(encoding="utf-8")

    assert 'if "record_subscription_usage_factory" in usage_source:' in source
    assert "legacy quota-account usage service is installed" in source
    assert "from processual_api.admin_marketplace.subscription_usage_service" not in source
