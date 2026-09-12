from __future__ import annotations

import asyncio

from processual_api.auth import platform_admin_bootstrap_env as bootstrap_env


def test_startup_bootstrap_checks_recovery_email_after_authority_exists(
    monkeypatch,
    capsys,
):
    async def authority_exists() -> bool:
        return True

    async def ensure_recovery_email() -> bool:
        return False

    monkeypatch.setattr(
        bootstrap_env,
        "_platform_admin_authority_exists",
        authority_exists,
    )
    monkeypatch.setattr(
        bootstrap_env,
        "_ensure_platform_admin_recovery_email",
        ensure_recovery_email,
    )
    monkeypatch.delenv(bootstrap_env.SECRET_ENV, raising=False)
    monkeypatch.delenv(bootstrap_env.SECRET_HASH_ENV, raising=False)

    assert asyncio.run(bootstrap_env._run()) == 0
    output = capsys.readouterr()
    assert "PlatformAdminBootstrapClosed=True" in output.out
    assert "PlatformAdminRecoveryEmailBackfilled=False" in output.out
    assert output.err == ""


def test_startup_bootstrap_reports_recovery_email_backfill(monkeypatch, capsys):
    async def authority_exists() -> bool:
        return True

    async def ensure_recovery_email() -> bool:
        return True

    monkeypatch.setattr(
        bootstrap_env,
        "_platform_admin_authority_exists",
        authority_exists,
    )
    monkeypatch.setattr(
        bootstrap_env,
        "_ensure_platform_admin_recovery_email",
        ensure_recovery_email,
    )

    assert asyncio.run(bootstrap_env._run()) == 0
    output = capsys.readouterr()
    assert "PlatformAdminBootstrapClosed=True" in output.out
    assert "PlatformAdminRecoveryEmailBackfilled=True" in output.out
    assert output.err == ""


def test_startup_bootstrap_fails_closed_when_first_bootstrap_env_is_incomplete(
    monkeypatch,
    capsys,
):
    async def authority_exists() -> bool:
        return False

    monkeypatch.setattr(
        bootstrap_env,
        "_platform_admin_authority_exists",
        authority_exists,
    )
    for name in (
        bootstrap_env.EMAIL_ENV,
        bootstrap_env.PASSWORD_ENV,
        bootstrap_env.SECRET_ENV,
        bootstrap_env.SECRET_HASH_ENV,
    ):
        monkeypatch.delenv(name, raising=False)

    assert asyncio.run(bootstrap_env._run()) == 5
    output = capsys.readouterr()
    assert "required for first platform-admin bootstrap" in output.err
    assert "PlatformAdminBootstrapCreated=True" not in output.out


def test_startup_bootstrap_does_not_print_secret_material(monkeypatch, capsys):
    async def authority_exists() -> bool:
        return False

    captured = {}

    async def bootstrap(environment) -> None:
        captured["environment"] = environment

    raw_secret = "render-one-time-bootstrap-secret-2026"
    password = "Render-admin-password-2026-strong"
    digest = "a" * 64
    monkeypatch.setattr(
        bootstrap_env,
        "_platform_admin_authority_exists",
        authority_exists,
    )
    monkeypatch.setattr(bootstrap_env, "_bootstrap", bootstrap)
    monkeypatch.setenv(bootstrap_env.EMAIL_ENV, "admin@example.com")
    monkeypatch.setenv(bootstrap_env.PASSWORD_ENV, password)
    monkeypatch.setenv(bootstrap_env.SECRET_ENV, raw_secret)
    monkeypatch.setenv(bootstrap_env.SECRET_HASH_ENV, digest)

    assert asyncio.run(bootstrap_env._run()) == 0
    output = capsys.readouterr()
    assert "PlatformAdminBootstrapCreated=True" in output.out
    assert "NextAction=login_and_complete_mfa" in output.out
    assert raw_secret not in output.out
    assert raw_secret not in output.err
    assert password not in output.out
    assert password not in output.err
    assert digest not in output.out
    assert digest not in output.err
    assert captured["environment"].bootstrap_secret == raw_secret
