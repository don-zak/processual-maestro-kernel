import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

import processual_api.routers.applications as applications_router


class FakeDiscordService:
    def __init__(self):
        self.alerts = []

    async def send_application_alert(self, payload, action="submitted", reviewer=None):
        self.alerts.append(
            {
                "payload": payload,
                "action": action,
                "reviewer": reviewer,
            }
        )


def run_async(coro):
    return asyncio.run(coro)


def patch_application_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(applications_router, "_DATA_DIR", tmp_path)

    fake_discord = FakeDiscordService()
    monkeypatch.setattr(applications_router, "_discord", lambda: fake_discord)

    return fake_discord


def test_application_storage_roundtrip_uses_json_files(tmp_path, monkeypatch):
    patch_application_storage(monkeypatch, tmp_path)

    apps = [
        {
            "id": "app-1",
            "status": "pending",
            "created_at": "2026-06-30T10:00:00+00:00",
            "applicant_type": "organization",
            "organization_name": "Acme",
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "linkedin_url": "",
            "company_url": "",
            "phone": "",
            "use_case": "Testing onboarding flow.",
            "agent_count": 3,
            "preferred_plan": "professional",
            "reviewed_at": None,
            "review_notes": None,
        }
    ]

    demos = [
        {
            "id": "demo-1",
            "application_id": "app-1",
            "email": "ada@example.com",
            "status": "active",
            "created_at": "2026-06-30T10:00:00+00:00",
            "expires_at": "2026-07-14T10:00:00+00:00",
            "evaluations_limit": 50,
            "evaluations_used": 0,
            "converted_at": None,
        }
    ]

    applications_router._save_apps(apps)
    applications_router._save_demos(demos)

    assert json.loads((tmp_path / "applications.json").read_text("utf-8")) == apps
    assert json.loads((tmp_path / "demos.json").read_text("utf-8")) == demos
    assert applications_router._load_apps() == apps
    assert applications_router._load_demos() == demos


def test_submit_application_validates_required_fields_and_email(tmp_path, monkeypatch):
    patch_application_storage(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as missing_name:
        run_async(
            applications_router.submit_application(
                applications_router.ApplicationRequest(
                    full_name="",
                    email="valid@example.com",
                    use_case="This is a valid use case.",
                )
            )
        )
    assert missing_name.value.status_code == 400
    assert "Full name" in missing_name.value.detail

    with pytest.raises(HTTPException) as invalid_email:
        run_async(
            applications_router.submit_application(
                applications_router.ApplicationRequest(
                    full_name="Ada Lovelace",
                    email="not-an-email",
                    use_case="This is a valid use case.",
                )
            )
        )
    assert invalid_email.value.status_code == 400
    assert "Invalid email" in invalid_email.value.detail

    with pytest.raises(HTTPException) as short_use_case:
        run_async(
            applications_router.submit_application(
                applications_router.ApplicationRequest(
                    full_name="Ada Lovelace",
                    email="ada@example.com",
                    use_case="short",
                )
            )
        )
    assert short_use_case.value.status_code == 400
    assert "use case" in short_use_case.value.detail


def test_submit_application_persists_pending_organization_request(tmp_path, monkeypatch):
    fake_discord = patch_application_storage(monkeypatch, tmp_path)

    response = run_async(
        applications_router.submit_application(
            applications_router.ApplicationRequest(
                applicant_type="organization",
                organization_name="Acme Labs",
                full_name="Ada Lovelace",
                email="ada@example.com",
                linkedin_url="https://example.com/ada",
                company_url="https://example.com",
                phone="+21600000000",
                use_case="We want to evaluate governed multi-agent workflows.",
                agent_count=5,
                preferred_plan="enterprise",
            )
        )
    )

    assert response.id.startswith("app_")
    assert response.status == "pending"
    assert response.applicant_type == "organization"
    assert response.organization_name == "Acme Labs"
    assert response.preferred_plan == "enterprise"

    stored = applications_router._load_apps()
    assert len(stored) == 1
    assert stored[0]["id"] == response.id
    assert stored[0]["status"] == "pending"
    assert stored[0]["preferred_plan"] == "enterprise"
    assert stored[0]["reviewed_at"] is None
    assert stored[0]["review_notes"] is None

    assert len(fake_discord.alerts) == 1
    assert fake_discord.alerts[0]["action"] == "submitted"
    assert fake_discord.alerts[0]["payload"]["preferred_plan"] == "enterprise"


def test_review_application_approve_creates_demo_and_blocks_second_review(
    tmp_path,
    monkeypatch,
):
    fake_discord = patch_application_storage(monkeypatch, tmp_path)

    app = run_async(
        applications_router.submit_application(
            applications_router.ApplicationRequest(
                full_name="Grace Hopper",
                email="grace@example.com",
                use_case="We need a governed evaluation demo for our technical team.",
                preferred_plan="professional",
            )
        )
    )

    approved = run_async(
        applications_router.review_application(
            app.id,
            applications_router.ApprovalAction(
                action="approve",
                notes="Approved for demo.",
            ),
            current_user={"sub": "admin@example.com"},
        )
    )

    assert approved.status == "approve"

    stored_apps = applications_router._load_apps()
    assert stored_apps[0]["status"] == "approve"
    assert stored_apps[0]["review_notes"] == "Approved for demo."
    assert stored_apps[0]["reviewed_at"] is not None

    demos = applications_router._load_demos()
    assert len(demos) == 1
    assert demos[0]["id"].startswith("demo_")
    assert demos[0]["application_id"] == app.id
    assert demos[0]["email"] == "grace@example.com"
    assert demos[0]["status"] == "active"
    assert demos[0]["evaluations_limit"] == 50
    assert demos[0]["evaluations_used"] == 0
    assert demos[0]["converted_at"] is None

    assert fake_discord.alerts[-1]["action"] == "approved"
    assert fake_discord.alerts[-1]["reviewer"] == "admin@example.com"

    with pytest.raises(HTTPException) as second_review:
        run_async(
            applications_router.review_application(
                app.id,
                applications_router.ApprovalAction(action="reject"),
                current_user={"sub": "admin@example.com"},
            )
        )
    assert second_review.value.status_code == 400
    assert "already" in second_review.value.detail


def test_review_application_rejects_without_creating_demo(tmp_path, monkeypatch):
    fake_discord = patch_application_storage(monkeypatch, tmp_path)

    app = run_async(
        applications_router.submit_application(
            applications_router.ApplicationRequest(
                full_name="Alan Turing",
                email="alan@example.com",
                use_case="We want to test a limited product evaluation path.",
            )
        )
    )

    rejected = run_async(
        applications_router.review_application(
            app.id,
            applications_router.ApprovalAction(
                action="reject",
                notes="Not a fit for demo.",
            ),
            current_user={"sub": "reviewer@example.com"},
        )
    )

    assert rejected.status == "reject"
    assert applications_router._load_demos() == []
    assert fake_discord.alerts[-1]["action"] == "rejected"
    assert fake_discord.alerts[-1]["reviewer"] == "reviewer@example.com"


def test_demo_check_validity_expiry_and_usage_limit(tmp_path, monkeypatch):
    patch_application_storage(monkeypatch, tmp_path)

    now = datetime.now(UTC)

    demos = [
        {
            "id": "demo-valid",
            "application_id": "app-valid",
            "email": "valid@example.com",
            "status": "active",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "evaluations_limit": 50,
            "evaluations_used": 10,
            "converted_at": None,
        },
        {
            "id": "demo-expired",
            "application_id": "app-expired",
            "email": "expired@example.com",
            "status": "active",
            "created_at": (now - timedelta(days=20)).isoformat(),
            "expires_at": (now - timedelta(days=1)).isoformat(),
            "evaluations_limit": 50,
            "evaluations_used": 10,
            "converted_at": None,
        },
        {
            "id": "demo-exceeded",
            "application_id": "app-exceeded",
            "email": "exceeded@example.com",
            "status": "active",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "evaluations_limit": 50,
            "evaluations_used": 50,
            "converted_at": None,
        },
        {
            "id": "demo-converted",
            "application_id": "app-converted",
            "email": "converted@example.com",
            "status": "converted",
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=3)).isoformat(),
            "evaluations_limit": 50,
            "evaluations_used": 10,
            "converted_at": now.isoformat(),
        },
    ]
    applications_router._save_demos(demos)

    valid = run_async(applications_router.check_demo("demo-valid"))
    assert valid["valid"] is True
    assert valid["expired"] is False
    assert valid["evaluations_exceeded"] is False

    expired = run_async(applications_router.check_demo("demo-expired"))
    assert expired["valid"] is False
    assert expired["expired"] is True
    assert expired["evaluations_exceeded"] is False

    exceeded = run_async(applications_router.check_demo("demo-exceeded"))
    assert exceeded["valid"] is False
    assert exceeded["expired"] is False
    assert exceeded["evaluations_exceeded"] is True

    converted = run_async(applications_router.check_demo("demo-converted"))
    assert converted["valid"] is False
    assert converted["status"] == "converted"

    missing = run_async(applications_router.check_demo("missing-demo"))
    assert missing == {"valid": False, "status": "not_found"}


def test_demo_usage_increment_updates_remaining_count(tmp_path, monkeypatch):
    patch_application_storage(monkeypatch, tmp_path)

    now = datetime.now(UTC)
    applications_router._save_demos(
        [
            {
                "id": "demo-usage",
                "application_id": "app-usage",
                "email": "usage@example.com",
                "status": "active",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=3)).isoformat(),
                "evaluations_limit": 3,
                "evaluations_used": 1,
                "converted_at": None,
            }
        ]
    )

    response = run_async(applications_router.increment_demo_usage("demo-usage"))

    assert response == {"incremented": True, "remaining": 1}
    assert applications_router._load_demos()[0]["evaluations_used"] == 2

    with pytest.raises(HTTPException) as missing_demo:
        run_async(applications_router.increment_demo_usage("missing-demo"))
    assert missing_demo.value.status_code == 404
    assert "Demo not found" in missing_demo.value.detail


def test_application_router_keeps_expected_onboarding_routes():
    source = (
        applications_router.Path(__file__).resolve().parents[1]
        / "processual_api"
        / "routers"
        / "applications.py"
    ).read_text(encoding="utf-8")

    required_markers = [
        'APIRouter(prefix="/applications"',
        '@router.post("", response_model=ApplicationResponse',
        '@router.get("/pending"',
        '@router.get("", response_model=ApplicationListResponse)',
        '@router.get("/{app_id}"',
        '@router.post("/{app_id}/review"',
        '@router.get("/{app_id}/demo"',
        '@router.get("/demo/check/{demo_id}"',
        '@router.post("/demo/{demo_id}/increment"',
        "preferred_plan",
        "evaluations_limit",
        "evaluations_used",
        "converted_at",
    ]

    missing = [marker for marker in required_markers if marker not in source]
    assert not missing, f"Missing application onboarding markers: {missing}"
