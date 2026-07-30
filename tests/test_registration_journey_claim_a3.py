from pathlib import Path

ROUTER = Path("processual_api/registration_journey/router.py")
CONTRACTS = Path("processual_api/registration_journey/contracts.py")
LOGIN = Path("processual_api/static/login.html")
REGISTER = Path("processual_api/static/register.html")
PLAN_DETAIL = Path("processual_api/static/plan_detail.html")


def test_a3_claim_sync_and_account_resume_routes_exist() -> None:
    text = ROUTER.read_text(encoding="utf-8")
    assert '@router.post("/intents/{intent_id}/claim"' in text
    assert '@router.post("/intents/{intent_id}/sync-account"' in text
    assert '@router.get("/intents/{intent_id}/account-resume"' in text
    assert "Depends(get_current_user)" in text


def test_a3_claim_requires_browser_binding_and_version() -> None:
    text = CONTRACTS.read_text(encoding="utf-8")
    assert "class IntentClaim" in text
    assert "session_token:" in text
    assert "version:" in text


def test_a3_cross_account_claim_is_denied() -> None:
    text = ROUTER.read_text(encoding="utf-8")
    assert "Journey already belongs to another account" in text
    assert "intent.user_id != user_id" in text


def test_a3_login_claims_existing_journey_after_authentication() -> None:
    text = LOGIN.read_text(encoding="utf-8")
    assert "/registration/intents/${journeyIntent}/claim" in text
    assert "pmk.registrationJourney.sessionToken" in text
    assert "Authorization" in text


def test_a3_registration_marks_email_verification_checkpoint() -> None:
    text = REGISTER.read_text(encoding="utf-8")
    assert "/registration/intents/${journeyIntent}/registration-accepted" in text
    assert "check_email" in text


def test_a3_does_not_enable_commercial_execution() -> None:
    text = ROUTER.read_text(encoding="utf-8").lower()
    for marker in (
        "/billing/checkout",
        "/billing/payment",
        "subscription activation",
        "entitlement grant",
        "webhook",
    ):
        assert marker not in text
