from __future__ import annotations

from fastapi import APIRouter, FastAPI

from tools import openapi_integrity


def _handler_payload() -> dict[str, bool]:
    return {"ok": True}


def test_audit_detects_duplicate_direct_routes(monkeypatch) -> None:
    test_app = FastAPI()
    test_app.add_api_route("/duplicate", _handler_payload, methods=["GET"])
    test_app.add_api_route("/duplicate", _handler_payload, methods=["GET"])
    monkeypatch.setattr(openapi_integrity, "app", test_app)

    payload = openapi_integrity.audit()

    assert payload["duplicate_routes"] == [("GET /duplicate", 2)]
    assert payload["ok"] is False


def test_audit_detects_duplicate_included_routes_with_effective_prefix(monkeypatch) -> None:
    child = APIRouter()
    child.add_api_route("/duplicate", _handler_payload, methods=["GET"])

    test_app = FastAPI()
    test_app.include_router(child, prefix="/nested")
    test_app.include_router(child, prefix="/nested")
    monkeypatch.setattr(openapi_integrity, "app", test_app)

    payload = openapi_integrity.audit()

    assert payload["duplicate_routes"] == [("GET /nested/duplicate", 2)]
    assert payload["ok"] is False
