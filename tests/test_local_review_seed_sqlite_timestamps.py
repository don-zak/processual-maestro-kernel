from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_local_review_seed_supplies_explicit_sqlite_timestamps():
    source = (ROOT / "qualification/local_review_subscription_seed.py").read_text(
        encoding="utf-8"
    )
    assert "now = datetime.now(UTC)" in source
    assert "created_at=now" in source
    assert "updated_at=now" in source
    assert "plan.updated_at = now" in source
    assert "subscription.updated_at = now" in source
    assert "runtime.updated_at = now" in source
    assert "sqlite+aiosqlite:///" in source
    assert "local review subscription seed is forbidden in production" in source
