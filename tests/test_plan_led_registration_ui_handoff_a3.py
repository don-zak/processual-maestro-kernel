from pathlib import Path

STATIC = Path("processual_api/static")
OFFER_JS = STATIC / "js" / "pages" / "offer.js"
REGISTER_JS = STATIC / "js" / "pages" / "register.js"


def test_direct_offer_uses_canonical_plan_id_registration_query() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")

    assert "/register?plan_id=" in source
    assert "/register?plan=" not in source


def test_assessment_offer_uses_apply_journey_not_registration() -> None:
    source = OFFER_JS.read_text(encoding="utf-8")

    assert "plan.requires_assessment || !plan.registration_available" in source
    assert "/apply?plan_id=" in source
    assert "journey=assessment" in source
    assert "/register?plan=${" not in source


def test_registration_controller_reads_optional_plan_id() -> None:
    source = REGISTER_JS.read_text(encoding="utf-8")

    assert "new URLSearchParams(window.location.search)" in source
    assert '.get("plan_id")' in source
    assert "payload.selected_plan_id = planId" in source


def test_registration_payload_does_not_send_client_price_fields() -> None:
    source = REGISTER_JS.read_text(encoding="utf-8")

    forbidden = (
        "amount_cents",
        "monthly_price_usd",
        "currency:",
        "offer_id",
        "checkout",
    )

    for marker in forbidden:
        assert marker not in source


def test_legacy_registration_remains_supported_without_plan_query() -> None:
    source = REGISTER_JS.read_text(encoding="utf-8")

    assert "return normalized || null" in source
    assert "if (planId)" in source
