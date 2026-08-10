from __future__ import annotations

import json
import re
from copy import deepcopy

import pytest

from processual_api.billing.customer_billing_statements import (
    BillingStatementIntegrityError,
    build_billing_statement,
    list_statements,
    load_statement,
    persist_statement,
    render_statement_pdf,
    statement_sha256,
)

CLIENT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_CLIENT_ID = "22222222-2222-2222-2222-222222222222"
ISSUED_AT = "2026-08-31T23:59:59+00:00"


def _cycle(**overrides):
    payload = {
        "plan_code": "business",
        "plan_catalog_version": "catalog-v1",
        "metric_code": "maestro_units",
        "period_start": "2026-08-01T00:00:00+00:00",
        "period_end": "2026-09-01T00:00:00+00:00",
        "base_limit_units": 100_000,
        "rollover_units": 5_000,
        "top_up_units": 50_000,
        "used_units": 12,
    }
    payload.update(overrides)
    return payload


def _top_up(**overrides):
    payload = {
        "purchase_ref": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "grant_ref": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "provider_reference": "provider-grant-1",
        "plan_code": "business",
        "plan_catalog_version": "catalog-v1",
        "purchased_at": "2026-08-10T10:00:00+00:00",
        "granted_at": "2026-08-10T10:05:00+00:00",
        "expires_at": "2026-09-01T00:00:00+00:00",
        "bundle_units": 25_000,
        "bundle_count": 2,
        "units_added": 50_000,
        "package_status": "active",
        "reversal_ref": None,
        "reversal_reason": None,
        "reversed_at": None,
        "reversal_units": 0,
        "net_units_added": 50_000,
        "total_price_usd": "42.00",
        "settlement_currency": "USD",
        "settlement_amount": "42.000",
        "channel": "lemon_squeezy",
        "exchange_rate_usd_tnd": None,
        "exchange_rate_source": None,
        "exchange_rate_reference": None,
    }
    payload.update(overrides)
    return payload


def _record(
    endpoint: str,
    endpoint_class: str,
    units: int,
    *,
    client_id: str = CLIENT_ID,
    period: str = "2026-08",
    status_code: int = 200,
    rejected: bool = False,
):
    return {
        "client_id": client_id,
        "endpoint": endpoint,
        "endpoint_class": endpoint_class,
        "units_charged": units,
        "quota_period": period,
        "status_code": status_code,
        "quota_rejected": rejected,
    }


def _statement(**overrides):
    kwargs = {
        "client_id": CLIENT_ID,
        "user_id": CLIENT_ID,
        "period": "2026-08",
        "usage_records": [
            _record("/cgt/analyze", "analysis_evaluation", 1),
            _record("/cgt/govern", "governance_evaluation", 1),
            _record("/cgt/govern/compare", "governance_evaluation", 2),
            _record("/reports/generate-llm", "report_generation", 5),
            _record(
                "/cgt/govern/auto-repair",
                "governance_evaluation",
                5,
                status_code=429,
                rejected=True,
            ),
            _record(
                "/billing/statements",
                "metered_api_request",
                1,
            ),
            _record(
                "/cgt/govern",
                "governance_evaluation",
                1,
                period="2026-07",
            ),
            _record(
                "/cgt/govern",
                "governance_evaluation",
                1,
                client_id=OTHER_CLIENT_ID,
            ),
        ],
        "quota_cycle": _cycle(used_units=12),
        "granted_top_ups": [_top_up()],
        "issued_at": ISSUED_AT,
    }
    kwargs.update(overrides)
    return build_billing_statement(**kwargs)


def test_statement_filters_period_client_and_only_explicit_maestro_metering():
    statement = _statement()

    assert statement["balance"] == {
        "base_allowance_units": 100_000,
        "rollover_units": 5_000,
        "top_up_units": 50_000,
        "available_units": 155_000,
        "consumed_units": 12,
        "remaining_units": 154_988,
    }

    items = {
        item["code"]: item
        for item in statement["usage_line_items"]
    }
    assert items["analysis_evaluation"]["maestro_units"] == 1
    assert items["governance_evaluation"]["maestro_units"] == 3
    assert items["report_generation"]["maestro_units"] == 5
    assert items["unattributed_authoritative_usage"]["maestro_units"] == 3
    assert "metered_api_request" not in items
    assert sum(item["maestro_units"] for item in items.values()) == 12
    assert round(sum(item["usage_percent"] for item in items.values()), 2) == 100.0


def test_rejected_attempts_are_explained_but_not_charged():
    statement = _statement()
    non_billable = statement["non_billable_activity"]
    assert non_billable["rejected_requests"] == 1
    assert non_billable["rejected_attempted_units"] == 5
    assert statement["balance"]["consumed_units"] == 12


def test_statement_fails_closed_when_ledger_exceeds_authoritative_usage():
    with pytest.raises(
        BillingStatementIntegrityError,
        match="billable ledger units exceed",
    ):
        _statement(quota_cycle=_cycle(used_units=8))


def test_statement_requires_top_up_detail_to_match_authoritative_net_units():
    with pytest.raises(
        BillingStatementIntegrityError,
        match="top-up detail and reversals",
    ):
        _statement(granted_top_ups=[])


def test_statement_preserves_purchase_and_explains_reversal():
    reversed_package = _top_up(
        package_status="reversed",
        reversal_ref="cccccccc-cccc-cccc-cccc-cccccccccccc",
        reversal_reason="provider_refund",
        reversed_at="2026-08-20T12:00:00+00:00",
        reversal_units=50_000,
        net_units_added=0,
    )
    statement = _statement(
        quota_cycle=_cycle(top_up_units=0, used_units=12),
        granted_top_ups=[reversed_package],
    )

    package = statement["additional_packages"][0]
    assert package["units_added"] == 50_000
    assert package["package_status"] == "reversed"
    assert package["reversal_units"] == 50_000
    assert package["net_units_added"] == 0
    assert statement["reconciliation"]["purchased_top_up_units"] == 50_000
    assert statement["reconciliation"]["reversed_top_up_units"] == 50_000
    assert statement["reconciliation"]["detailed_top_up_units"] == 0
    assert statement["reconciliation"]["top_ups_reconciled"] is True


def test_manual_review_reversal_keeps_units_available_until_authority_changes():
    package = _top_up(
        package_status="manual_review",
        reversal_ref="dddddddd-dddd-dddd-dddd-dddddddddddd",
        reversal_reason="units_already_consumed",
        reversed_at="2026-08-20T12:00:00+00:00",
        reversal_units=0,
        net_units_added=50_000,
    )
    statement = _statement(granted_top_ups=[package])
    assert statement["additional_packages"][0]["package_status"] == "manual_review"
    assert statement["balance"]["top_up_units"] == 50_000


def test_duplicate_or_invalid_bundle_geometry_is_rejected():
    duplicate = deepcopy(_top_up())
    with pytest.raises(BillingStatementIntegrityError, match="duplicate"):
        _statement(granted_top_ups=[_top_up(), duplicate])

    with pytest.raises(BillingStatementIntegrityError, match="bundle geometry"):
        _statement(
            granted_top_ups=[_top_up(bundle_count=3)],
        )


def test_statement_sha_is_deterministic_and_changes_with_payload():
    first = _statement()
    second = _statement()
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first["statement_sha256"])
    assert first["statement_sha256"] == statement_sha256(first)

    changed = deepcopy(first)
    changed["balance"]["remaining_units"] -= 1
    assert statement_sha256(changed) != first["statement_sha256"]


def test_persistence_is_immutable_and_tamper_evident(tmp_path):
    statement = _statement()
    persisted = persist_statement(tmp_path, statement)
    assert persist_statement(tmp_path, statement) == persisted
    assert load_statement(tmp_path, statement["statement_ref"]) == statement

    path = (
        tmp_path
        / "billing_statements"
        / f"{statement['statement_ref']}.json"
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["balance"]["remaining_units"] -= 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        BillingStatementIntegrityError,
        match="SHA-256",
    ):
        load_statement(tmp_path, statement["statement_ref"])


def test_statement_listing_filters_clients_and_skips_tampered_snapshots(tmp_path):
    client_statement = _statement()
    other_statement = _statement(
        client_id=OTHER_CLIENT_ID,
        user_id=OTHER_CLIENT_ID,
        usage_records=[],
        quota_cycle=_cycle(used_units=0, top_up_units=0),
        granted_top_ups=[],
    )
    persist_statement(tmp_path, client_statement)
    persist_statement(tmp_path, other_statement)

    assert [
        item["client_id"]
        for item in list_statements(tmp_path, client_id=CLIENT_ID)
    ] == [CLIENT_ID]

    other_path = (
        tmp_path
        / "billing_statements"
        / f"{other_statement['statement_ref']}.json"
    )
    payload = json.loads(other_path.read_text(encoding="utf-8"))
    payload["plan"]["plan_id"] = "tampered"
    other_path.write_text(json.dumps(payload), encoding="utf-8")
    assert all(
        item["client_id"] != OTHER_CLIENT_ID
        for item in list_statements(tmp_path)
    )


def test_pdf_is_generated_from_verified_snapshot():
    pytest.importorskip("reportlab")
    statement = _statement()
    pdf = render_statement_pdf(statement)
    assert pdf.startswith(b"%PDF")

    tampered = deepcopy(statement)
    tampered["plan"]["plan_id"] = "tampered"
    with pytest.raises(
        BillingStatementIntegrityError,
        match="invalid SHA-256",
    ):
        render_statement_pdf(tampered)
