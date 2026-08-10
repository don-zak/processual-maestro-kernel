from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from processual_api.billing import router as billing_router

CLIENT_ID = "11111111-1111-1111-1111-111111111111"
OTHER_CLIENT_ID = "22222222-2222-2222-2222-222222222222"


def _summary_statement(client_id: str = CLIENT_ID):
    return {
        "statement_ref": "MUS-2026-08-client-abc123",
        "statement_sha256": "a" * 64,
        "issued_at": "2026-08-31T23:59:59+00:00",
        "client_id": client_id,
        "user_id": client_id,
        "billing_period": {"period": "2026-08"},
        "plan": {"plan_id": "business"},
        "balance": {
            "consumed_units": 1200,
            "remaining_units": 98800,
            "top_up_units": 0,
        },
        "additional_packages": [],
        "reconciliation": {
            "reconciled": True,
            "top_ups_reconciled": True,
        },
    }


def _client_user(client_id: str = CLIENT_ID):
    return {
        "user_id": client_id,
        "sub": client_id,
        "role": "client",
    }


def test_billing_statement_routes_are_registered():
    paths = {
        (method, route.path)
        for route in billing_router.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
    }
    expected = {
        ("GET", "/billing/statements"),
        ("POST", "/billing/statements/{period}"),
        ("GET", "/billing/statements/{statement_ref}"),
        ("GET", "/billing/statements/{statement_ref}/pdf"),
        ("GET", "/billing/admin/statements"),
        ("POST", "/billing/admin/statements/{client_id}/{period}"),
        ("GET", "/billing/admin/statements/{statement_ref}"),
        ("GET", "/billing/admin/statements/{statement_ref}/pdf"),
    }
    assert expected.issubset(paths)


def test_customer_statement_listing_is_scoped_to_authenticated_identity(monkeypatch):
    captured = {}

    def fake_list(data_dir, *, client_id=None):
        captured["client_id"] = client_id
        return [_summary_statement(client_id)]

    monkeypatch.setattr(billing_router, "list_statements", fake_list)
    payload = asyncio.run(
        billing_router.list_customer_billing_statements(
            _client_user()
        )
    )
    assert captured["client_id"] == CLIENT_ID
    assert payload["client_id"] == CLIENT_ID
    assert payload["statement_count"] == 1
    assert payload["statements"][0]["client_id"] == CLIENT_ID
    assert payload["statements"][0]["pdf_url"].startswith(
        "/billing/statements/"
    )


def test_customer_cannot_read_or_download_another_customer_statement(monkeypatch):
    monkeypatch.setattr(
        billing_router,
        "_load_verified_statement",
        lambda ref: _summary_statement(OTHER_CLIENT_ID),
    )

    with pytest.raises(HTTPException) as read_exc:
        asyncio.run(
            billing_router.get_customer_billing_statement(
                "foreign",
                _client_user(),
            )
        )
    assert read_exc.value.status_code == 404

    with pytest.raises(HTTPException) as pdf_exc:
        asyncio.run(
            billing_router.download_customer_billing_statement_pdf(
                "foreign",
                _client_user(),
            )
        )
    assert pdf_exc.value.status_code == 404


def test_billing_admin_authority_is_fail_closed():
    with pytest.raises(HTTPException) as exc:
        billing_router._require_billing_admin(
            {"role": "client", "scopes": []}
        )
    assert exc.value.status_code == 403

    billing_router._require_billing_admin(
        {"role": "billing_admin", "scopes": []}
    )
    billing_router._require_billing_admin(
        {"role": "service", "scopes": ["admin:billing:read"]}
    )


def test_statement_issuance_is_idempotent_for_same_client_period(monkeypatch):
    existing = _summary_statement()
    authority_called = False

    def fake_list(data_dir, *, client_id=None):
        assert client_id == CLIENT_ID
        return [existing]

    async def forbidden_authority(**kwargs):
        nonlocal authority_called
        authority_called = True
        raise AssertionError("authority should not be re-read")

    monkeypatch.setattr(billing_router, "list_statements", fake_list)
    monkeypatch.setattr(
        billing_router,
        "load_billing_authority_snapshot",
        forbidden_authority,
    )

    result = asyncio.run(
        billing_router._issue_statement(
            client_id=CLIENT_ID,
            user_id=CLIENT_ID,
            period="2026-08",
        )
    )
    assert result is existing
    assert authority_called is False


def test_duplicate_immutable_statements_for_period_fail_closed(monkeypatch):
    first = _summary_statement()
    second = dict(first, statement_ref="MUS-2026-08-client-def456")
    monkeypatch.setattr(
        billing_router,
        "list_statements",
        lambda data_dir, client_id=None: [first, second],
    )

    with pytest.raises(HTTPException) as exc:
        billing_router._existing_period_statement(
            client_id=CLIENT_ID,
            period="2026-08",
        )
    assert exc.value.status_code == 409


def test_pdf_response_has_pdf_content_type_and_sha_header(monkeypatch):
    statement = _summary_statement()
    monkeypatch.setattr(
        billing_router,
        "render_statement_pdf",
        lambda payload: b"%PDF-test",
    )
    response = billing_router._pdf_response(statement)
    assert response.media_type == "application/pdf"
    assert response.body == b"%PDF-test"
    assert response.headers["x-maestro-statement-sha256"] == "a" * 64
    assert "attachment" in response.headers["content-disposition"]


def test_missing_pdf_dependency_is_reported_as_503(monkeypatch):
    monkeypatch.setattr(
        billing_router,
        "render_statement_pdf",
        lambda payload: (_ for _ in ()).throw(
            RuntimeError("missing reports")
        ),
    )
    with pytest.raises(HTTPException) as exc:
        billing_router._pdf_response(_summary_statement())
    assert exc.value.status_code == 503


def test_admin_statement_summary_uses_admin_pdf_gateway():
    summary = billing_router._statement_summary(
        _summary_statement(),
        admin=True,
    )
    assert summary["pdf_url"].startswith(
        "/billing/admin/statements/"
    )
