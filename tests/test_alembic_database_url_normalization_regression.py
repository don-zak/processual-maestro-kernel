from __future__ import annotations

from pathlib import Path

ENV = Path("alembic/env.py")


def test_alembic_database_url_is_trimmed_and_postgres_aliases_are_normalized() -> None:
    text = ENV.read_text(encoding="utf-8")

    assert "url = raw.strip()" in text
    assert 'url.startswith("postgresql+asyncpg://")' in text
    assert 'url.startswith("postgresql://")' in text
    assert 'url.startswith("postgres://")' in text
    assert '"postgresql+asyncpg://"' in text


def test_alembic_database_url_rejects_empty_and_control_characters() -> None:
    text = ENV.read_text(encoding="utf-8")

    assert 'raise RuntimeError("DATABASE_URL is not configured.")' in text
    assert 'raise RuntimeError("DATABASE_URL is empty.")' in text
    assert "any(ord(ch) < 32 or ord(ch) == 127 for ch in url)" in text
    assert 'raise RuntimeError("DATABASE_URL contains control characters.")' in text
