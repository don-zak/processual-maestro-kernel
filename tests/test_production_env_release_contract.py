from pathlib import Path


ENV_PATH = Path(__file__).resolve().parents[1] / ".env.production.example"


def _production_env_text() -> str:
    return ENV_PATH.read_text(encoding="utf-8")


def test_production_env_contract_has_release_evidence_and_cloud_run_port_guidance() -> None:
    text = _production_env_text()

    assert "MIGRATION_BACKUP_REFERENCE=" in text
    assert "MIGRATION_RESTORE_REHEARSAL_REFERENCE=" in text
    assert "Google Cloud Run injects PORT at runtime" in text
    assert "${PORT:-8000}" in text


def test_production_env_contract_rejects_legacy_lemon_squeezy_plan_variants() -> None:
    text = _production_env_text()
    legacy_keys = (
        "LS_VARIANT_STARTER=",
        "LS_VARIANT_STARTER_YEARLY=",
        "LS_VARIANT_PROFESSIONAL=",
        "LS_VARIANT_PROFESSIONAL_YEARLY=",
        "LS_VARIANT_ENTERPRISE=",
        "LS_VARIANT_ENTERPRISE_YEARLY=",
    )

    assert not any(key in text for key in legacy_keys)


def test_tunisia_local_top_up_remains_fail_closed_in_production_template() -> None:
    text = _production_env_text()

    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED=false" in text
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED=false" in text
    assert "MAESTRO_TUNISIA_FX_OBSERVED_AT=" in text
    assert "authoritative FX source observation" in text
