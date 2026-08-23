from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "lemon_squeezy_provider_qualification_contract.json"
SCRIPT = ROOT / "scripts" / "Test-PMKLemonSqueezyProviderPreflight.ps1"
DOC = ROOT / "docs" / "LEMON_SQUEEZY_REAL_PROVIDER_QUALIFICATION.md"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_provider_contract_preserves_authority_boundaries() -> None:
    contract = _contract()
    assert contract["provider"] == "lemon_squeezy"
    assert contract["status"] == "PREPARED_FOR_REAL_PROVIDER_EXECUTION"
    assert contract["secrets_recorded"] is False
    assert contract["real_provider_qualified"] is False
    assert contract["real_staging_qualified"] is False
    assert contract["production_authority_granted"] is False
    assert contract["commercial_launch"] == "NO_GO"


def test_provider_contract_requires_exact_external_configuration_names() -> None:
    assert _contract()["required_environment"] == [
        "LEMONSQUEEZY_API_KEY",
        "LEMONSQUEEZY_WEBHOOK_SECRET",
        "LEMONSQUEEZY_STORE_ID",
    ]


def test_provider_contract_reuses_existing_authoritative_commercial_paths() -> None:
    contract = _contract()
    for relative in contract["required_repository_contracts"]:
        assert (ROOT / relative).is_file(), relative
    assert "processual_api/admin_marketplace/lemon_squeezy_secure_webhook_router.py" in contract["required_repository_contracts"]
    assert "processual_api/admin_marketplace/subscription_activation_service.py" in contract["required_repository_contracts"]
    assert "processual_api/admin_marketplace/subscription_authoritative_quota_bootstrap.py" in contract["required_repository_contracts"]


def test_real_provider_evidence_covers_commercial_success_replay_and_mismatch_paths() -> None:
    evidence = set(_contract()["required_real_provider_evidence"])
    assert {
        "test_mode_store_access",
        "api_key_authenticated_request",
        "verified_offer_variant_binding",
        "https_webhook_delivery",
        "valid_webhook_signature",
        "authoritative_order_ref_match",
        "provider_customer_ownership_match",
        "provider_variant_match",
        "amount_currency_match",
        "webhook_replay_idempotency",
        "subscription_activation",
        "authoritative_quota_bootstrap",
        "refund_or_cancellation_lifecycle",
        "provider_failure_fail_closed",
    } <= evidence


def test_preflight_never_serializes_secret_values_and_keeps_real_authority_false() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "LEMONSQUEEZY_API_KEY" in source
    assert "LEMONSQUEEZY_WEBHOOK_SECRET" in source
    assert "LEMONSQUEEZY_STORE_ID" in source
    assert "secret_values_recorded = $false" in source
    assert "real_provider_qualified = $false" in source
    assert "real_staging_qualified = $false" in source
    assert "production_authority_granted = $false" in source
    assert "commercial_launch = \"NO_GO\"" in source
    assert "api_key =" not in source.lower()
    assert "webhook_secret =" not in source.lower()


def test_documentation_requires_signed_webhook_and_authoritative_activation_chain() -> None:
    doc = DOC.read_text(encoding="utf-8")
    assert "/billing/webhook" in doc
    assert "authoritative internal order reference" in doc
    assert "subscription activation" in doc
    assert "authoritative quota bootstrap" in doc
    assert "RealProviderQualified=false" in doc
