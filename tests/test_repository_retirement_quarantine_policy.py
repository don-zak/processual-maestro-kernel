from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "governance" / "repository_retirement_quarantine.json"
CLIENT_ALIAS = ROOT / "processual_api" / "routers" / "client_provider_alias_18.py"
PROVIDER_RUNTIME = ROOT / "processual_api" / "routers" / "settings_provider_test_runtime.py"
PUBLIC_SURFACES = (
    ROOT / "processual_api" / "static" / "plans.html",
    ROOT / "processual_api" / "static" / "offer.html",
    ROOT / "processual_api" / "static" / "js" / "pages" / "plans.js",
    ROOT / "processual_api" / "static" / "js" / "pages" / "offer.js",
)


def _policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_quarantine_policy_preserves_protected_history_and_disables_auto_deletion() -> None:
    policy = _policy()

    assert policy["authority"]["repository_reconciliation_complete"] is False
    assert policy["authority"]["real_staging_qualified"] is False
    assert policy["authority"]["production_authority_granted"] is False
    assert policy["evidence_closeout"]["deletion_authorized"] is False
    assert "alembic/versions/" in policy["protected_path_prefixes"]
    assert "tests/" in policy["protected_path_prefixes"]
    assert "docs/" in policy["protected_path_prefixes"]
    assert "qualification/" in policy["protected_path_prefixes"]
    assert all(item["deletion_allowed"] is False for item in policy["tracked_surfaces"])


def test_review_decision_closeout_records_identity_complete_but_not_exact_history() -> None:
    review = _policy()["evidence_closeout"]["review_decisions"]

    assert review["classification"] == "LATEST_IDENTITY_COMPLETE_WITH_HISTORICAL_PAYLOAD_CHANGES"
    assert review["latest_version"] == 8
    assert review["latest_item_count"] == 57
    assert review["all_historical_identity_count"] == 57
    assert review["identities_missing_from_latest"] == 0
    assert review["every_transition_identity_monotonic"] is True
    assert review["every_transition_exact_monotonic"] is False
    assert review["historical_versions_must_be_preserved"] is True


def test_cgt17_closeout_records_three_exact_duplicate_pairs_without_deletion_authority() -> None:
    evidence = _policy()["evidence_closeout"]["cgt17_retirement_evidence"]

    assert evidence["classification"] == "THREE_EXACT_DUPLICATE_PAIRS"
    assert evidence["file_count"] == 6
    assert evidence["distinct_sha256_count"] == 3
    assert evidence["historical_files_must_be_preserved"] is True
    assert len(evidence["pairs"]) == 3
    assert all(len(pair) == 2 for pair in evidence["pairs"])


def test_client_provider_alias_remains_explicitly_deprecated_and_non_primary() -> None:
    policy = _policy()
    entry = next(
        item
        for item in policy["tracked_surfaces"]
        if item["path"] == "processual_api/routers/client_provider_alias_18.py"
    )
    source = CLIENT_ALIAS.read_text(encoding="utf-8")

    assert entry["classification"] == "COMPATIBILITY_HOLD"
    assert entry["primary_authority"] is False
    assert entry["deletion_allowed"] is False
    assert entry["successor_surface"] == "/settings/provider-connection"
    assert "deprecated=True" in source
    assert 'response.headers["Deprecation"] = "true"' in source
    assert 'response.headers["X-Maestro-Replacement"] = "/settings/provider-connection"' in source


def test_legacy_provider_test_endpoint_cannot_regain_primary_authority() -> None:
    policy = _policy()
    entry = next(
        item
        for item in policy["tracked_surfaces"]
        if item["path"] == "processual_api/routers/settings_provider_test_runtime.py"
    )
    source = PROVIDER_RUNTIME.read_text(encoding="utf-8")

    assert entry["classification"] == "ACTIVE_RUNTIME_WITH_DEPRECATED_COMPATIBILITY"
    assert entry["successor_surface"] == "/settings/provider-connection/test"
    assert '"/provider-connection/test"' in source
    assert '"/llm-provider/test"' in source
    assert "deprecated=True" in source
    assert "successor-version" in source


def test_retired_enterprise_plan_ids_are_forbidden_from_public_surfaces() -> None:
    policy = _policy()
    symbols = policy["retired_public_symbols"][0]

    assert symbols["classification"] == "HISTORICAL_COMPATIBILITY_ONLY"
    assert symbols["public_reintroduction_forbidden"] is True
    assert symbols["deletion_allowed"] is False

    public_text = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_SURFACES)
    for symbol in symbols["symbols"]:
        assert symbol not in public_text
