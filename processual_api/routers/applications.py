"""Apply & Approval flow — B2B application, manual review, demo activation."""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth.security import get_current_user
from ..dependencies import file_lock
from ..services.discord_service import DiscordService

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

router = APIRouter(prefix="/applications", tags=["applications"])


# ─── Schemas ───

class ApplicationRequest(BaseModel):
    applicant_type: str = "professional"  # "organization" | "professional"
    organization_name: str = ""
    full_name: str
    email: str
    linkedin_url: str = ""
    company_url: str = ""
    phone: str = ""
    use_case: str
    agent_count: int | None = None
    preferred_plan: str = "professional"  # "starter" | "professional" | "enterprise"


class ApplicationResponse(BaseModel):
    id: str
    status: str  # "pending" | "approved" | "rejected"
    created_at: str
    applicant_type: str
    full_name: str
    email: str
    organization_name: str
    linkedin_url: str
    use_case: str
    preferred_plan: str


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationResponse]
    total: int


class ApprovalAction(BaseModel):
    action: str  # "approve" | "reject"
    notes: str = ""


class DemoInfo(BaseModel):
    application_id: str
    status: str  # "active" | "expired" | "converted"
    expires_at: str
    evaluations_limit: int
    evaluations_used: int
    days_remaining: int | None = None


# ─── Storage ───

def _apps_path() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / "applications.json"


def _demos_path() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / "demos.json"


def _load_apps() -> list[dict]:
    path = _apps_path()
    if path.exists():
        with file_lock(path):
            try:
                return json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return []


def _save_apps(apps: list[dict]):
    path = _apps_path()
    with file_lock(path):
        path.write_text(json.dumps(apps, indent=2, ensure_ascii=False), "utf-8")


def _load_demos() -> list[dict]:
    path = _demos_path()
    if path.exists():
        with file_lock(path):
            try:
                return json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return []


def _save_demos(demos: list[dict]):
    path = _demos_path()
    with file_lock(path):
        path.write_text(json.dumps(demos, indent=2, ensure_ascii=False), "utf-8")


# ─── Helpers ───

def _validate_email(email: str) -> bool:
    return "@" in email and "." in email.split("@")[-1]


def _discord() -> DiscordService:
    return DiscordService()


# ─── Endpoints ───

@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def submit_application(body: ApplicationRequest):
    if not body.full_name or not body.email:
        raise HTTPException(status_code=400, detail="Full name and email are required")
    if not _validate_email(body.email):
        raise HTTPException(status_code=400, detail="Invalid email address")
    if not body.use_case or len(body.use_case.strip()) < 10:
        raise HTTPException(status_code=400, detail="Please describe your use case (at least 10 characters)")

    apps = _load_apps()

    app_id = f"app_{secrets.token_hex(8)}"
    now = datetime.now(UTC).isoformat()

    entry = {
        "id": app_id,
        "status": "pending",
        "created_at": now,
        "applicant_type": body.applicant_type,
        "organization_name": body.organization_name,
        "full_name": body.full_name,
        "email": body.email,
        "linkedin_url": body.linkedin_url,
        "company_url": body.company_url,
        "phone": body.phone,
        "use_case": body.use_case,
        "agent_count": body.agent_count,
        "preferred_plan": body.preferred_plan,
        "reviewed_at": None,
        "review_notes": None,
    }

    apps.append(entry)
    _save_apps(apps)

    await _discord().send_application_alert(
        {"full_name": body.full_name, "email": body.email, "preferred_plan": body.preferred_plan,
         "applicant_type": body.applicant_type, "use_case": body.use_case, "linkedin_url": body.linkedin_url},
        action="submitted",
    )

    return ApplicationResponse(
        id=app_id,
        status="pending",
        created_at=now,
        applicant_type=body.applicant_type,
        full_name=body.full_name,
        email=body.email,
        organization_name=body.organization_name,
        linkedin_url=body.linkedin_url,
        use_case=body.use_case,
        preferred_plan=body.preferred_plan,
    )


@router.get("/pending", response_model=ApplicationListResponse)
async def list_pending_applications(current_user: dict = Depends(get_current_user)):
    apps = _load_apps()
    pending = [a for a in apps if a.get("status") == "pending"]
    return ApplicationListResponse(
        applications=[ApplicationResponse(**a) for a in pending],
        total=len(pending),
    )


@router.get("", response_model=ApplicationListResponse)
async def list_all_applications(current_user: dict = Depends(get_current_user)):
    apps = _load_apps()
    return ApplicationListResponse(
        applications=[ApplicationResponse(**a) for a in apps],
        total=len(apps),
    )


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(app_id: str, current_user: dict = Depends(get_current_user)):
    apps = _load_apps()
    for a in apps:
        if a["id"] == app_id:
            return ApplicationResponse(**a)
    raise HTTPException(status_code=404, detail="Application not found")


@router.post("/{app_id}/review", response_model=ApplicationResponse)
async def review_application(app_id: str, body: ApprovalAction, current_user: dict = Depends(get_current_user)):
    apps = _load_apps()
    for a in apps:
        if a["id"] != app_id:
            continue
        if a["status"] != "pending":
            raise HTTPException(status_code=400, detail=f"Application already {a['status']}")

        a["status"] = body.action
        a["reviewed_at"] = datetime.now(UTC).isoformat()
        a["review_notes"] = body.notes
        _save_apps(apps)

        reviewer = current_user.get("sub", "unknown")

        if body.action == "approve":
            _create_demo(app_id, a.get("email", "unknown"))
            await _discord().send_application_alert(a, action="approved", reviewer=reviewer)
        else:
            await _discord().send_application_alert(a, action="rejected", reviewer=reviewer)

        return ApplicationResponse(**a)

    raise HTTPException(status_code=404, detail="Application not found")


# ─── Demo Service ───

def _create_demo(application_id: str, email: str) -> dict:
    demos = _load_demos()
    demo_id = f"demo_{secrets.token_hex(8)}"
    now = datetime.now(UTC)
    expires = now + timedelta(days=14)

    entry = {
        "id": demo_id,
        "application_id": application_id,
        "email": email,
        "status": "active",
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "evaluations_limit": 50,
        "evaluations_used": 0,
        "converted_at": None,
    }

    demos.append(entry)
    _save_demos(demos)
    return entry


@router.get("/{app_id}/demo", response_model=DemoInfo)
async def get_demo(app_id: str, current_user: dict = Depends(get_current_user)):
    demos = _load_demos()
    for d in demos:
        if d["application_id"] == app_id:
            now = datetime.now(UTC)
            expires = datetime.fromisoformat(d["expires_at"])
            days_remaining = max(0, (expires - now).days)
            return DemoInfo(
                application_id=app_id,
                status=d["status"],
                expires_at=d["expires_at"],
                evaluations_limit=d["evaluations_limit"],
                evaluations_used=d.get("evaluations_used", 0),
                days_remaining=days_remaining,
            )
    raise HTTPException(status_code=404, detail="Demo not found for this application")


@router.get("/demo/check/{demo_id}", response_model=dict)
async def check_demo(demo_id: str):
    """Public endpoint to check demo validity (no auth required)."""
    demos = _load_demos()
    for d in demos:
        if d["id"] == demo_id:
            now = datetime.now(UTC)
            expires = datetime.fromisoformat(d["expires_at"])
            evaluations = d.get("evaluations_used", 0)
            limit = d["evaluations_limit"]

            expired = now > expires
            exceeded = evaluations >= limit

            return {
                "valid": d["status"] == "active" and not expired and not exceeded,
                "status": d["status"],
                "expired": expired,
                "evaluations_exceeded": exceeded,
                "evaluations_used": evaluations,
                "evaluations_limit": limit,
                "days_remaining": max(0, (expires - now).days),
            }
    return {"valid": False, "status": "not_found"}


@router.post("/demo/{demo_id}/increment", response_model=dict)
async def increment_demo_usage(demo_id: str):
    """Called internally when a CGT evaluation is made under a demo."""
    demos = _load_demos()
    for d in demos:
        if d["id"] == demo_id:
            d["evaluations_used"] = d.get("evaluations_used", 0) + 1
            _save_demos(demos)
            remaining = max(0, d["evaluations_limit"] - d["evaluations_used"])
            return {"incremented": True, "remaining": remaining}
    raise HTTPException(status_code=404, detail="Demo not found")
