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
    assert 'op.f("ck_evaluation_runtime_delivery_state")' in source
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


def test_postgres_store_uses_typed_transactional_authority() -> None:
    source = _read(
        "processual_api/services/evaluation_runtime_delivery_postgres.py"
    )

    assert "from sqlalchemy.dialects.postgresql import insert as pg_insert" in source
    assert "EvaluationRuntimeDelivery" in source
    assert ".on_conflict_do_nothing()" in source
    assert ".with_for_update()" in source
    assert "text(" not in source
    assert "INSERT INTO" not in source
    assert "raw_task_input_persisted=False" in source
    assert "raw_secret_visible=False" in source


def test_delivery_model_is_registered_with_shared_metadata() -> None:
    model_source = _read(
        "processual_api/services/evaluation_runtime_delivery_models.py"
    )
    alembic_env = _read("alembic/env.py")

    assert 'class EvaluationRuntimeDelivery(Base):' in model_source
    assert '__tablename__ = "evaluation_runtime_delivery"' in model_source
    assert 'name="uq_evaluation_runtime_delivery_authority_key"' in model_source
    assert 'name="state"' in model_source
    assert "evaluation_runtime_delivery_models" in alembic_env
