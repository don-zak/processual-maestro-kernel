from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_delivery_migration_extends_current_head() -> None:
    source = _read(
        "alembic/versions/20260901_0048_evaluation_runtime_delivery_ledger.py"
    )

    assert 'revision: str = "20260901_0048"' in source
    assert 'down_revision: str | None = "20260830_0047"' in source
    assert 'TABLE = "evaluation_runtime_delivery"' in source
    assert 'name="uq_evaluation_runtime_delivery_authority_key"' in source
    assert 'name="ck_evaluation_runtime_delivery_state"' in source
    assert 'sa.Column("replay_response", sa.JSON(), nullable=True)' in source
    assert 'sa.Column("evidence", sa.JSON(), nullable=True)' in source
    assert "raw_task_input" not in source.replace("raw_task_input_persisted", "")
    assert "raw_secret" not in source.replace("raw_secret_visible", "")


def test_runtime_uses_shared_postgres_delivery_authority() -> None:
    source = _read("processual_api/routers/evaluation_runtime.py")

    assert "evaluation_runtime_delivery_postgres import" in source
    assert "await claim_evaluation_execution(" in source
    assert "await complete_evaluation_execution(" in source
    assert "await fail_evaluation_execution(" in source
    assert "from processual_api.services.evaluation_runtime_delivery import" not in source


def test_postgres_store_claims_with_database_uniqueness() -> None:
    source = _read(
        "processual_api/services/evaluation_runtime_delivery_postgres.py"
    )

    assert "INSERT INTO" in source
    assert "ON CONFLICT DO NOTHING" in source
    assert "FOR UPDATE" in source
    assert "CAST(:replay_response AS JSONB)" in source
    assert "CAST(:evidence AS JSONB)" in source
    assert "raw_task_input_persisted = false" in source
    assert "raw_secret_visible = false" in source
