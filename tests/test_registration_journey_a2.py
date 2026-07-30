from pathlib import Path


def test_a2_domain_and_migration_exist() -> None:
    for relative in (
        "processual_api/registration_journey/contracts.py",
        "processual_api/registration_journey/models.py",
        "processual_api/registration_journey/router.py",
        "alembic/versions/20260730_0017_registration_journey.py",
    ):
        assert Path(relative).exists()


def test_a2_router_has_persistent_resume_and_no_commercial_execution() -> None:
    text = Path("processual_api/registration_journey/router.py").read_text(encoding="utf-8")
    assert '@router.post("/intents"' in text
    assert '@router.patch("/intents/{intent_id}"' in text
    assert '@router.get("/intents/{intent_id}/resume"' in text
    for forbidden in ("/billing/checkout", "webhook", "entitlement grant"):
        assert forbidden not in text.lower()


def test_plan_detail_creates_journey_before_registration() -> None:
    text = Path("processual_api/static/plan_detail.html").read_text(encoding="utf-8")
    assert 'fetch("/registration/intents"' in text
    assert "sessionStorage" in text
    assert 'target.searchParams.set("journey_intent", intent.intent_id)' in text


def test_register_reads_selected_plan_context() -> None:
    text = Path("processual_api/static/register.html").read_text(encoding="utf-8")
    assert 'id="selected-plan-context"' in text
    assert 'params.get("journey_intent")' in text
