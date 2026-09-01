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
    assert "showcase_decision_journey.js?v=decision-journey-p5" in auth
    assert "showcase_decision_receipt.js?v=decision-receipt-p5" in auth
    assert "showcase_decision_motion.js?v=decision-motion-p2" in auth
    assert "showcase_guided_flow.js?v=guided-flow-p5" in auth
    assert "showcase_cinematic_transitions.js?v=cinematic-p4" in auth
    assert "data-maestro-decision-journey" in auth
    assert "data-maestro-decision-receipt" in auth
    assert "data-maestro-decision-motion" in auth
    assert "data-maestro-guided-flow" in auth
    assert "data-maestro-cinematic-transitions" in auth
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
        "Execution",
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
        "Execution paused. Human approval is required before governed execution.",
        "Human approval recorded. Governed execution admitted",
        "Governed execution completed. Finalizing auditable evidence",
        "Approval recorded → governed execution → evidence retained",
        "Qualified fallback executed inside policy boundary → evidence retained",
        "Fail closed → no execution granted",
        "DEMO UI · deterministic sequence",
        "does not claim live production execution",
    ):
        assert label in journey

    assert "{ id: 'execution', label: 'Execution'" in journey
    assert "data-mdj-step=\"execution\"" in journey
    assert "stopAt: 'approval'" in journey
    assert "stopAt: 'evidence'" in journey
    assert journey.count("stopAt: 'governance'") == 1
    assert "data-mdj-approve" in journey
    assert "production-ready" not in journey.lower()


def test_decision_receipt_makes_evidence_visible_without_claiming_production() -> None:
    receipt = (STATIC_ROOT / "js" / "showcase_decision_receipt.js").read_text(
        encoding="utf-8"
    )

    for label in (
        "DECISION RECEIPT",
        "DEMO RECEIPT · synthetic evidence view",
        "Demo operator",
        "Governed scope",
        "Raw secret",
        "Not included",
        "Approval recorded",
        "Governed execution · evidence retained",
        "Qualified fallback executed",
        "Fallback executed · evidence retained",
        "Execution denied",
        "It is not a live production audit record",
    ):
        assert label in receipt

    assert "MutationObserver" in receipt
    assert "decision === 'CONTROL'" in receipt
    assert "decision === 'REPAIR'" in receipt
    assert "decision === 'STOP'" in receipt
    assert "production-ready" not in receipt.lower()


def test_decision_motion_emphasizes_active_path_and_respects_reduced_motion() -> None:
    motion = (STATIC_ROOT / "js" / "showcase_decision_motion.js").read_text(
        encoding="utf-8"
    )

    assert ".mdj-node.active .mdj-node-core::after" in motion
    assert ".mdj-pulse::after" in motion
    assert "height:6px!important" in motion
    assert "@keyframes mdj-node-wave" in motion
    assert "@keyframes mdj-pulse-head" in motion
    assert "prefers-reduced-motion:reduce" in motion


def test_guided_showcase_keeps_presenter_in_control_and_follows_story_order() -> None:
    guided = (STATIC_ROOT / "js" / "showcase_guided_flow.js").read_text(
        encoding="utf-8"
    )

    for label in (
        "Start guided showcase",
        "Presenter guide · manual control",
        "01 · Problem → Authority",
        "02 · Decision Journey",
        "03 · Governed Outcomes",
        "04 · Qualification Evidence",
        "Run CONTROL first",
        "Human Approval, then cross governed Execution before Evidence",
        "CONTROL, REPAIR, and STOP",
        "live owned HTTPS proof visibly separate",
        "Next →",
        "← Back",
        "Exit",
    ):
        assert label in guided

    assert "page: 'overview'" in guided
    assert "page: 'governance'" in guided
    assert "page: 'reports'" in guided
    assert "[data-msv2=\"hero\"]" in guided
    assert "[data-mdj=\"journey\"]" in guided
    assert "[data-msv2=\"recorded-evidence\"]" in guided
    assert "[data-msv2=\"qualification\"]" in guided
    assert "setInterval(" not in guided
    assert "autoplay" not in guided.lower()
    assert "prefers-reduced-motion:reduce" in guided


def test_cinematic_transition_layer_is_visual_only_and_guided_flow_bound() -> None:
    cinematic = (STATIC_ROOT / "js" / "showcase_cinematic_transitions.js").read_text(
        encoding="utf-8"
    )

    for label in (
        "mct-guided-active",
        "mct-stage-label",
        "mct-page-enter",
        "mct-hero-reveal",
        "mct-stage-rise",
        "mct-focus-breathe",
        "prefers-reduced-motion:reduce",
    ):
        assert label in cinematic

    assert "document.querySelector('.mgf-panel')" in cinematic
    assert "panel.classList.contains('active')" in cinematic
    assert "MutationObserver" in cinematic
    assert "setInterval(" not in cinematic
    assert "autoplay" not in cinematic.lower()
    assert "data-page" not in cinematic
    assert ".click()" not in cinematic