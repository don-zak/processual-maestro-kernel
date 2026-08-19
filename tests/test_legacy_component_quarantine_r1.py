from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSUAL_API = ROOT / "processual_api"


def test_production_code_does_not_import_compatibility_subscription_catalog() -> None:
    forbidden = "processual_api.billing.subscription_catalog"
    offenders: list[str] = []

    for path in PROCESSUAL_API.rglob("*.py"):
        if path.as_posix().endswith("processual_api/billing/subscription_catalog.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_production_code_does_not_depend_on_deprecated_provider_alias_route() -> None:
    forbidden = "/client/provider-connection"
    alias_path = PROCESSUAL_API / "routers/client_provider_alias_18.py"
    offenders: list[str] = []

    for path in PROCESSUAL_API.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".js", ".html"}:
            continue
        if path == alias_path:
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden in text:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_quarantined_console_assets_remain_present_only_for_review() -> None:
    paths = (
        "processual_api/static/js/adapters/governor.js",
        "processual_api/static/js/adapters/cgt.js",
        "processual_api/static/js/pages/governor.js",
        "processual_api/static/js/pages/cgt.js",
    )

    for relative in paths:
        assert (ROOT / relative).is_file(), relative


def test_quarantine_register_does_not_misclassify_active_legacy_router_as_dead() -> None:
    register = (
        ROOT / "docs/qualification/LEGACY_COMPONENT_QUARANTINE_REGISTER_R1.md"
    ).read_text(encoding="utf-8")

    assert "`processual_api/routers/cgt_governor.py` | `ACTIVE_LEGACY_DEBT`" in register
    assert "explicitly **not** a deletion candidate" in register
