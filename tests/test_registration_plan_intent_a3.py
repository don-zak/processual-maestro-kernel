import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from processual_api.auth.models import AuthRegistrationPlanIntent, IdentityUser
from processual_api.auth.registration_repository import SqlAlchemyRegistrationRepository


def test_registration_plan_intent_is_separate_from_identity_user_columns():
    user_columns = {column.name for column in IdentityUser.__table__.columns}
    intent_columns = {column.name for column in AuthRegistrationPlanIntent.__table__.columns}

    assert "plan_id" not in user_columns
    assert "selected_plan_id" not in user_columns
    assert {"user_id", "selected_plan_id", "state", "verified_at"}.issubset(intent_columns)


def test_repository_persists_selected_plan_as_pending_intent():
    session = Mock()
    repository = SqlAlchemyRegistrationRepository(session)
    now = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)
    user_id = uuid.uuid4()

    repository.add_registration(
        user_id=user_id,
        email_normalized="plan@example.com",
        display_name="Plan User",
        password_hash="$argon2id$encoded",
        terms_version="2026-08",
        accepted_at=now,
        action_token_id=uuid.uuid4(),
        action_token_hash="a" * 64,
        action_token_expires_at=now + timedelta(hours=24),
        selected_plan_id="starter",
    )

    added = [call.args[0] for call in session.add.call_args_list]
    intent = next(item for item in added if isinstance(item, AuthRegistrationPlanIntent))
    user = next(item for item in added if isinstance(item, IdentityUser))

    assert intent.user_id == user_id
    assert intent.selected_plan_id == "starter"
    assert intent.state == "pending_verification"
    assert intent.verified_at is None
    assert intent.user is user


def test_repository_preserves_legacy_registration_without_plan_intent():
    session = Mock()
    repository = SqlAlchemyRegistrationRepository(session)
    now = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)

    repository.add_registration(
        user_id=uuid.uuid4(),
        email_normalized="legacy@example.com",
        display_name="Legacy User",
        password_hash="$argon2id$encoded",
        terms_version="2026-08",
        accepted_at=now,
        action_token_id=uuid.uuid4(),
        action_token_hash="b" * 64,
        action_token_expires_at=now + timedelta(hours=24),
    )

    added = [call.args[0] for call in session.add.call_args_list]
    assert not any(isinstance(item, AuthRegistrationPlanIntent) for item in added)


def test_registration_plan_intent_migration_extends_current_head():
    source = Path(
        "alembic/versions/20260803_0015_registration_plan_intent.py"
    ).read_text(encoding="utf-8")

    assert 'revision: str = "20260803_0015"' in source
    assert 'down_revision: str | None = "20260729_0014"' in source
    assert '"auth_registration_plan_intents"' in source
    assert '"selected_plan_id"' in source
    assert "pending_verification" in source
    assert "verified" in source
