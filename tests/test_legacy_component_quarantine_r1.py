from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSUAL_API = ROOT / "processual_api"
QUARANTINED_CONSOLE_ASSETS = (
    "processual_api/static/js/adapters/governor.js",
    "processual_api/static/js/adapters/cgt.js",
    "processual_api/static/js/pages/governor.js",
    "processual_api/static/js/pages/cgt.js",
)
QUARANTINED_ROOT_ARTIFACTS = (
    "readiness_report.html",
)


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


def _find_production_surface_references(
    forbidden: str,
    *,
    allowed_paths: set[Path],
) -> list[str]:
    offenders: list[str] = []
    for path in PROCESSUAL_API.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".js", ".html"}:
            continue
        if path in allowed_paths:
            continue
        text = path.read_text(encoding="utf-8")
        if forbidden in text:
            offenders.append(str(path.relative_to(ROOT)))
    return offenders


def test_production_code_does_not_depend_on_deprecated_provider_alias_route() -> None:
    alias_path = PROCESSUAL_API / "routers/client_provider_alias_18.py"
    assert _find_production_surface_references(
        "/client/provider-connection",
        allowed_paths={alias_path},
    ) == []


def test_production_code_does_not_depend_on_deprecated_provider_test_route() -> None:
    runtime_path = PROCESSUAL_API / "routers/settings_provider_test_runtime.py"
    assert _find_production_surface_references(
        "/settings/llm-provider/test",
        allowed_paths={runtime_path},
    ) == []


def test_production_code_does_not_reintroduce_legacy_credit_conversion_helper() -> None:
    maestro_units_path = PROCESSUAL_API / "billing/maestro_units.py"
    assert _find_production_surface_references(
        "credits_from_maestro_units",
        allowed_paths={maestro_units_path},
    ) == []


def test_quarantined_console_assets_remain_present_only_for_review() -> None:
    for relative in QUARANTINED_CONSOLE_ASSETS:
        assert (ROOT / relative).is_file(), relative


def test_public_runtime_image_explicitly_removes_quarantined_console_assets() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    removal_block = dockerfile.split("RUN rm -f", 1)[1].split("RUN test ! -d", 1)[0]

    for relative in QUARANTINED_CONSOLE_ASSETS:
        assert relative in removal_block
        assert f"test ! -e {relative}" in removal_block


def test_quarantined_root_readiness_artifacts_never_enter_runtime_image() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    copy_lines = [line.strip() for line in dockerfile.splitlines() if line.strip().startswith("COPY ")]

    assert "COPY . ." not in copy_lines
    for relative in QUARANTINED_ROOT_ARTIFACTS:
        assert (ROOT / relative).is_file(), relative
        assert all(relative not in line for line in copy_lines), relative


def test_quarantine_register_does_not_misclassify_active_legacy_router_as_dead() -> None:
    register = (
        ROOT / "docs/qualification/LEGACY_COMPONENT_QUARANTINE_REGISTER_R1.md"
    ).read_text(encoding="utf-8")

    assert "`processual_api/routers/cgt_governor.py` | `ACTIVE_LEGACY_DEBT`" in register
    assert "explicitly **not** a deletion candidate" in register
