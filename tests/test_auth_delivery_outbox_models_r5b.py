from __future__ import annotations

from sqlalchemy import create_engine, inspect

from processual_api.auth.models import AuthDeliveryOutbox
from processual_api.db.base import Base


def test_delivery_outbox_is_ciphertext_only_and_idempotent_per_action_token() -> None:
    columns = {column.name for column in AuthDeliveryOutbox.__table__.columns}
    assert {
        "user_id",
        "action_token_id",
        "event_type",
        "payload_ciphertext",
        "payload_key_version",
        "available_at",
        "attempt_count",
        "claimed_at",
        "delivered_at",
        "last_error_code",
    }.issubset(columns)
    assert columns.isdisjoint(
        {
            "email",
            "email_normalized",
            "raw_action_token",
            "action_token",
            "payload_plaintext",
        }
    )
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in AuthDeliveryOutbox.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("action_token_id",) in unique_columns


def test_delivery_outbox_metadata_creates_and_drops_with_identity_tables() -> None:
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        Base.metadata.create_all(connection)
        assert "auth_delivery_outbox" in inspect(connection).get_table_names()
        Base.metadata.drop_all(connection)
        assert "auth_delivery_outbox" not in inspect(connection).get_table_names()
