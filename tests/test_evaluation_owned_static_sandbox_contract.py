from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_SANDBOX = ROOT / "deployment" / "evaluation-owned-sandbox-static"


def test_static_owned_sandbox_customer_fixture_is_deterministic_and_synthetic() -> None:
    payload = json.loads((STATIC_SANDBOX / "public" / "users" / "1.json").read_text(encoding="utf-8"))

    assert payload["id"] == 1
    assert payload["username"] == "sandbox-customer-001"
    assert payload["name"] == "Processual Sandbox Customer"
    assert payload["email"].endswith("@example.invalid")
    assert payload["company"]["name"] == "Processual Evaluation Telecom"
    assert "Synthetic" in payload["company"]["catchPhrase"]


def test_static_owned_sandbox_health_is_explicitly_nonproduction() -> None:
    payload = json.loads((STATIC_SANDBOX / "public" / "health" / "live.json").read_text(encoding="utf-8"))

    assert payload == {
        "status": "ok",
        "service": "processual-maestro-evaluation-sandbox-static",
        "production_allowed": False,
        "synthetic_data_only": True,
    }


def test_netlify_and_vercel_preserve_extensionless_qualification_routes() -> None:
    netlify = (STATIC_SANDBOX / "netlify.toml").read_text(encoding="utf-8")
    vercel = json.loads((STATIC_SANDBOX / "vercel.json").read_text(encoding="utf-8"))

    assert 'from = "/users/1"' in netlify
    assert 'to = "/users/1.json"' in netlify
    assert 'from = "/health/live"' in netlify
    assert 'to = "/health/live.json"' in netlify
    assert 'Cache-Control = "no-store"' in netlify

    rewrites = {(item["source"], item["destination"]) for item in vercel["rewrites"]}
    assert ("/users/1", "/users/1.json") in rewrites
    assert ("/health/live", "/health/live.json") in rewrites
    assert all(
        any(header["key"] == "Cache-Control" and header["value"] == "no-store" for header in rule["headers"])
        for rule in vercel["headers"]
    )
