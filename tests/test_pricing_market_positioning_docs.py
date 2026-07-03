from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reports" / "MAESTRO_PRICING_MARKET_POSITIONING.md"


def test_pricing_market_positioning_document_exists():
    assert DOC.exists()


def test_pricing_market_positioning_documents_byok_and_market_refs():
    text = DOC.read_text(encoding="utf-8")

    assert "PRICING-MARKET-01" in text
    assert "BYOK" in text
    assert "Maestro usage units" in text

    for reference in (
        "Langfuse",
        "Portkey",
        "Helicone",
        "LangSmith",
        "Braintrust",
        "Kong",
    ):
        assert reference in text


def test_pricing_market_positioning_documents_allowance_ladder():
    text = DOC.read_text(encoding="utf-8")

    expected_rows = {
        "developer": "2,000",
        "starter": "10,000",
        "business": "100,000",
        "enterprise_integration_starter": "50,000",
        "enterprise_integration": "500,000",
        "enterprise_custom": "configurable",
    }

    for plan, allowance in expected_rows.items():
        assert plan in text
        assert allowance in text


def test_pricing_market_positioning_blocks_50k_as_full_enterprise():
    text = DOC.read_text(encoding="utf-8")

    assert "50,000 Maestro units/month should not be presented as the main Enterprise" in text
    assert "enterprise_integration_starter = 50,000 units/month" in text
    assert "enterprise_integration = 500,000 units/month" in text
    assert "avoid embedding USD prices in backend enforcement logic" in text
