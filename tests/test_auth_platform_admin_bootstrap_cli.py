from pathlib import Path


BOOTSTRAP = Path("processual_api/auth/platform_admin_bootstrap.py")


def test_platform_admin_bootstrap_cli_initializes_and_closes_database() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")

    assert "from processual_api.db.session import close_db, get_session_factory, init_db" in source
    assert "await init_db()" in source
    assert "session_factory = get_session_factory()" in source
    assert "SqlAlchemyPlatformAdminBootstrapUnitOfWork(\n                session_factory" in source
    assert "finally:\n        await close_db()" in source


def test_platform_admin_bootstrap_cli_reports_missing_database_configuration() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")

    assert "Platform administrator bootstrap database is unavailable." in source
    assert "Set DATABASE_URL to the identity database before running bootstrap." in source
    assert "return 7" in source
