from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "site" / "index.html"


def test_public_site_is_static_and_has_product_identity() -> None:
    source = SITE.read_text(encoding="utf-8")
    assert "Processual Maestro" in source
    assert "Govern • Supervise • Calibrate • Orchestrate" in source
    assert "AI governance and orchestration" in source
    assert "https://github.com/don-zak/processual-maestro-kernel" in source


def test_public_site_preserves_release_authority_boundary() -> None:
    source = SITE.read_text(encoding="utf-8")
    assert "controlled qualification" in source.lower()
    assert "Real staging and production authority remain separate qualification gates" in source
    assert "No production-launch claim" in source


def test_public_site_does_not_embed_runtime_secrets() -> None:
    source = SITE.read_text(encoding="utf-8")
    forbidden = (
        "LEMONSQUEEZY_API_KEY=",
        "LEMONSQUEEZY_WEBHOOK_SECRET=",
        "JWT_SECRET=",
        "API_KEYS=",
        "BEGIN PRIVATE KEY",
    )
    assert not [marker for marker in forbidden if marker in source]
