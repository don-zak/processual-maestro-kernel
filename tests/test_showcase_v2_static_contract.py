from pathlib import Path


STATIC_ROOT = Path("processual_api/static")


def test_public_splash_uses_demo_safe_claims_and_contact_address() -> None:
    splash = (STATIC_ROOT / "splash.html").read_text(encoding="utf-8")

    assert "contact@zaxam.net" in splash
    assert "mailto:contact@zaxam.net" in splash
    assert "Interactive Demo" in splash
    assert "Interactive demo ready" in splash
    assert "Production Ready" not in splash
    assert "جاهز للإنتاج" not in splash


def test_maestro_console_loads_showcase_enhancements_without_replacing_console() -> None:
    auth = (STATIC_ROOT / "js" / "auth.js").read_text(encoding="utf-8")
    index = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")

    assert "showcase_v2.js?v=showcase-v2-p0" in auth
    # Guard the complete console markup that was present before the enhancement.
    assert 'id="page-governor"' in index
    assert 'id="gw-summary"' in index
    assert 'id="page-simulation"' in index
    assert 'id="page-settings"' in index
    assert 'id="set-integration-readiness-card"' in index


def test_showcase_p0_cues_are_explicit_and_fail_safe() -> None:
    showcase = (STATIC_ROOT / "js" / "showcase_v2.js").read_text(encoding="utf-8")

    for label in (
        "Actor",
        "Authority",
        "Commercial Rights",
        "Quota",
        "Governance",
        "Human Approval",
        "Execution",
        "Evidence",
        "CONTROL",
        "REPAIR",
        "STOP",
        "RECORDED QUALIFICATION EVIDENCE",
        "Operational Admission Impact",
        "Quota used",
        "Quota remaining",
        "Latest admission status",
        "auditable evidence",
        "Public CI",
        "Security",
        "Deep Integrity",
        "Pre-External Readiness",
        "SHA-bound qualification",
        "Live owned HTTPS proof - separate gate",
        "contact@zaxam.net",
    ):
        assert label in showcase

    assert "set-usage-quota-used" in showcase
    assert "set-usage-quota-remaining" in showcase
    assert "set-usage-latest-status" in showcase
    assert "MutationObserver" in showcase
    assert "CI-qualified demo" in showcase
    assert "production-ready" not in showcase.lower()
