from __future__ import annotations

import inspect
from datetime import timedelta
from pathlib import Path

from processual_api.admin_marketplace.identity_authority import (
    AdminMarketplaceIdentityAuthorityResolver,
)
from processual_api.auth.mfa_service import MfaService


ROOT = Path(__file__).resolve().parents[1]


def test_mfa_service_default_step_up_window_is_fifteen_minutes() -> None:
    default = inspect.signature(MfaService.__init__).parameters["step_up_ttl"].default
    assert default == timedelta(minutes=15)


def test_admin_marketplace_default_step_up_window_is_fifteen_minutes() -> None:
    default = inspect.signature(
        AdminMarketplaceIdentityAuthorityResolver.__init__
    ).parameters["mfa_step_up_max_age"].default
    assert default == timedelta(minutes=15)


def test_canonical_settings_default_is_nine_hundred_seconds() -> None:
    source = (ROOT / "processual_api/settings.py").read_text(encoding="utf-8")
    assert 'os.environ.get("AUTH_MFA_STEP_UP_SECONDS", "900")' in source
    assert 'os.environ.get("AUTH_MFA_STEP_UP_SECONDS", "300")' not in source


def test_deployment_and_production_example_use_fifteen_minutes() -> None:
    production_env = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    render_blueprint = (
        ROOT / "deployment/external-evaluation-authority/render.yaml"
    ).read_text(encoding="utf-8")

    assert "AUTH_MFA_STEP_UP_SECONDS=900" in production_env
    assert "AUTH_MFA_STEP_UP_SECONDS=300" not in production_env
    assert "- key: AUTH_MFA_STEP_UP_SECONDS\n        value: 900" in render_blueprint


def test_mfa_step_up_safety_bounds_remain_one_to_thirty_minutes() -> None:
    service_source = (ROOT / "processual_api/auth/mfa_service.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (ROOT / "processual_api/auth/mfa_runtime.py").read_text(
        encoding="utf-8"
    )

    assert "step_up_ttl < timedelta(minutes=1)" in service_source
    assert "step_up_ttl > timedelta(minutes=30)" in service_source
    assert "step_up_ttl < timedelta(minutes=1)" in runtime_source
    assert "step_up_ttl > timedelta(minutes=30)" in runtime_source
