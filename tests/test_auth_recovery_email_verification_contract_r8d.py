import importlib.util
from pathlib import Path

from processual_api.auth.models import (
    AuthActionToken,
    AuthDeliveryOutbox,
)


def test_models_allow_recovery_email_verification_values():
    action_constraints = " ".join(
        str(constraint.sqltext)
        for constraint in AuthActionToken.__table__.constraints
        if hasattr(constraint, "sqltext")
    )

    delivery_constraints = " ".join(
        str(constraint.sqltext)
        for constraint in AuthDeliveryOutbox.__table__.constraints
        if hasattr(constraint, "sqltext")
    )

    assert "verify_recovery_email" in action_constraints
    assert "verify_recovery_email" in delivery_constraints


def test_migration_extends_and_restores_constraints():
    root = Path(__file__).resolve().parents[1]

    candidates = [
        root
        / "alembic"
        / "versions"
        / "20260723_0008_recovery_email_verification_tokens.py",
        root
        / "migrations"
        / "versions"
        / "20260723_0008_recovery_email_verification_tokens.py",
    ]

    migration = next(
        path for path in candidates if path.is_file()
    )

    source = migration.read_text(encoding="utf-8")

    assert 'revision = "20260723_0008"' in source
    assert 'down_revision = "20260723_0007"' in source
    assert "verify_recovery_email" in source
    assert "purpose_allowed" in source
    spec = importlib.util.spec_from_file_location(
        "auth_r8d_0008_migration",
        migration,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.ACTION_CONSTRAINT == (
        "ck_auth_action_tokens_"
        "ck_auth_action_tokens_purpose_allowed"
    )
    assert module.DELIVERY_CONSTRAINT == (
        "ck_auth_delivery_outbox_"
        "ck_auth_delivery_outbox_event_t_8c12"
    )


def test_repository_and_service_never_persist_raw_token():
    root = Path(__file__).resolve().parents[1]

    repository_source = (
        root
        / "processual_api"
        / "auth"
        / "recovery_email_verification_repository.py"
    ).read_text(encoding="utf-8")

    service_source = (
        root
        / "processual_api"
        / "auth"
        / "recovery_email_verification_service.py"
    ).read_text(encoding="utf-8")

    assert "token_hash=verification.digest" in service_source
    assert "token_hash: str" in repository_source
    assert "raw_token=" not in repository_source
    assert 'purpose="verify_recovery_email"' in service_source
    assert 'event_type="verify_recovery_email"' in repository_source
