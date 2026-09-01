from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_evaluation_runtime_uses_shared_authority_not_local_settings() -> None:
    runtime = (ROOT / "processual_api/routers/evaluation_runtime.py").read_text(encoding="utf-8")

    assert "load_evaluation_authority_state" in runtime
    assert "settings_router._load_raw" not in runtime
    assert "settings_router._save_raw" not in runtime
    assert "Shared Evaluation runtime authority is unavailable" in runtime


def test_evaluation_admin_uses_postgres_for_grants_keys_and_revocation() -> None:
    routes = (ROOT / "processual_api/routers/settings_admin_evaluation_grants.py").read_text(
        encoding="utf-8"
    )

    assert "save_evaluation_authority_state" in routes
    assert "load_evaluation_authority_state" in routes
    assert "create_evaluation_authority_key" in routes
    assert "revoke_evaluation_authority_grant" in routes
    assert '"authority_store": "postgresql_shared"' in routes
    # Local settings may be read once only to seal already-prepared sandbox configuration.
    assert routes.count("settings_module._load_raw") == 1
    assert "settings_module._save_raw" not in routes


def test_security_is_shared_first_and_production_fail_closed() -> None:
    security = (ROOT / "processual_api/auth/security.py").read_text(encoding="utf-8")

    assert "verify_evaluation_api_key" in security
    assert "await verify_evaluation_api_key(api_key)" in security
    assert "except EvaluationAuthorityError" in security
    assert "_legacy_get_current_user" in security
    assert "Evaluation API key is not present in shared authority" in security


def test_shared_authority_snapshot_contains_only_evaluation_runtime_inputs() -> None:
    store = (ROOT / "processual_api/services/evaluation_authority_postgres.py").read_text(
        encoding="utf-8"
    )

    for storage_key in (
        "evaluation_grants_v1",
        "enterprise_endpoint_bindings_v1",
        "enterprise_endpoint_request_mappings_v1",
        "enterprise_endpoint_sandbox_grants_v1",
        "enterprise_sandbox_secret_references_v1",
        "enterprise_sandbox_content_contracts_v1",
        "enterprise_endpoint_sandbox_evidence_v1",
    ):
        assert storage_key in store

    assert '"api_keys"' not in store.split("def evaluation_authority_snapshot", 1)[1].split(
        "async def save_evaluation_authority_state", 1
    )[0]
    assert '"production_allowed": False' in store
