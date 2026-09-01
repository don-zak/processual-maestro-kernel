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

    assert "showcase_v2.js?v=showcase-v2-p1" in auth
    assert "showcase_decision_journey.js?v=decision-journey-p2" in auth
    assert "data-maestro-decision-journey" in auth
    # Guard the complete console markup that was present before the enhancement.
    assert 'id="page-governor"' in index
    assert 'id="gw-summary"' in index
    assert 'id="page-simulation"' in index
    assert 'id="page-settings"' in index
    assert 'id="set-integration-readiness-card"' in index


def test_showcase_enterprise_narrative_is_explicit_and_fail_safe() -> None:
    showcase = (STATIC_ROOT / "js" / "showcase_v2.js").read_text(encoding="utf-8")

    for label in (
        "Agentic Operations & Governance Control Plane",
        "Capability is not",
        "When an AI agent can perform a real operational action",
        "DEMO UI",
        "RECORDED EVIDENCE",
        "TECHNICAL QUALIFICATION",
        "deterministic synthetic interaction",
        "qualified governance outcomes",
        "CI and integrity gates",
        "View governed outcomes",
        "View qualification evidence",
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
        "SLA incident governance",
        "Provider degradation recovery",
        "Sensitive configuration change",
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

    assert "data-msv2-nav=\"governance\"" in showcase
    assert "data-msv2-nav=\"reports\"" in showcase
    assert "set-usage-quota-used" in showcase
    assert "set-usage-quota-remaining" in showcase
    assert "set-usage-latest-status" in showcase
    assert "MutationObserver" in showcase
    assert "CI-qualified demo" in showcase
    assert "production-ready" not in showcase.lower()


def test_decision_journey_is_deterministic_governed_and_demo_safe() -> None:
    journey = (STATIC_ROOT / "js" / "showcase_decision_journey.js").read_text(
        encoding="utf-8"
    )

    for label in (
        "Governed Decision Journey",
        "Identity",
        "Authority",
        "Entitlement",
        "Quota",
        "Capacity",
        "Governance",
        "Human Approval",
        "Evidence",
        "SLA incident governance",
        "Provider degradation recovery",
        "Sensitive configuration change",
        "CONTROL",
        "REPAIR",
        "STOP",
        "Human approval required",
        "Qualified fallback available",
        "Outside approved maintenance window",
        "Execution paused. Human approval is required before evidence finalization.",
        "Human approval recorded. Finalizing auditable evidence",
        "Approval recorded → evidence retained",
        "Fallback selected inside policy boundary",
        "Fail closed → no execution granted",
        "DEMO UI · deterministic sequence",
        "does not claim live production execution",
    ):
        assert label in journey

    assert "stopAt: 'approval'" in journey
    assert "stopAt: 'governance'" in journey
    assert "data-mdj-approve" in journey
    assert "data-mdj-step=\"evidence\"" not in journey
    assert "production-ready" not in journey.lower()
