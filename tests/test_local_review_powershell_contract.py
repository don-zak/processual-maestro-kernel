from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_local_review_environment_is_development_sqlite_only():
    source = read("scripts/local_review_env.ps1")
    assert '$env:ENVIRONMENT = "development"' in source
    assert '$env:APP_ENV = "development"' in source
    assert 'sqlite+aiosqlite:///' in source
    assert '$env:PMK_LOCAL_REVIEW_CUSTOMER_REF = "admin"' in source
    assert 'Python 3.14+' in source


def test_bootstrap_orders_migration_before_seed_and_supports_reset():
    source = read("scripts/bootstrap_local_review.ps1")
    assert '[switch]$ResetDatabase' in source
    assert 'python -m alembic upgrade head' in source
    assert 'qualification/local_review_subscription_seed.py' in source
    assert source.index('python -m alembic upgrade head') < source.index(
        'qualification/local_review_subscription_seed.py'
    )
    assert 'Remove-Item -LiteralPath $context.DatabasePath -Force' in source


def test_run_script_orchestrates_bootstrap_and_uvicorn_without_authority_promotion():
    source = read("scripts/run_local_review.ps1")
    assert '[switch]$ResetDatabase' in source
    assert '[switch]$OpenBrowser' in source
    assert 'bootstrap_local_review.ps1' in source
    assert 'python -m uvicorn processual_api.main:app' in source
    assert '127.0.0.1' in source
    assert 'This launcher grants no staging or production authority.' in source


def test_health_check_covers_runtime_and_ui_routes():
    source = read("scripts/check_local_review.ps1")
    assert '/health/live' in source
    assert '/health/ready' in source
    assert '/console/' in source
    assert '/admin' in source


def test_setup_installs_only_required_local_review_extras():
    source = read("scripts/setup_local_review.ps1")
    assert 'pip install -e ".[api,security,database]"' in source
    assert 'run_local_review.ps1 -ResetDatabase -OpenBrowser' in source
