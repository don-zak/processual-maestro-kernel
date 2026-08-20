from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_subscription_runtime_accepts_bounded_authenticated_subject_reference():
    source = read("processual_api/routers/settings_subscription_runtime.py")
    assert 'str(candidate or "").strip().lower()' in source
    assert "len(normalized) > 128" in source
    assert "uuid.UUID" not in source
    assert 'detail="Subscription access denied."' in source


def test_local_review_seed_is_sqlite_only_and_production_forbidden():
    source = read("qualification/local_review_subscription_seed.py")
    assert "settings.is_production" in source
    assert "forbidden in production" in source
    assert 'startswith("sqlite+aiosqlite:///")' in source
    assert 'PLAN_CODE = "enterprise_integration_starter"' in source
    assert '"production_authority": "false"' in source
    assert 'access_stage="active"' in source
    assert "runtime_connector_approved=false production_allowed=false" in source


def test_powershell_local_review_launcher_orders_database_seed_before_server():
    source = read("scripts/run_local_review.ps1")
    migration = "python -m alembic upgrade head"
    seed = "python qualification/local_review_subscription_seed.py"
    server = "python -m uvicorn processual_api.main:app"
    assert 'sqlite+aiosqlite:///$dbUrlPath' in source
    assert '$env:ENVIRONMENT = "development"' in source
    assert '$env:PMK_LOCAL_REVIEW_CUSTOMER_REF = "admin"' in source
    assert '$env:MAESTRO_ADMIN_EMAIL = $null' in source
    assert '$env:MAESTRO_ADMIN_PASSWORD = $null' in source
    assert migration in source
    assert seed in source
    assert server in source
    assert source.index(migration) < source.index(seed) < source.index(server)
