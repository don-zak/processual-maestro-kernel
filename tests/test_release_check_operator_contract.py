from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_check.py"


def test_release_check_does_not_auto_declare_production_readiness() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "STATIC PRE-RELEASE CHECKS PASS" in text
    assert "operator/runtime qualification is still required" in text
    assert 'print("RESULT: RELEASE READY' not in text


def test_release_check_verifies_public_image_boundary() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert '"--target", "public"' in text
    assert "test ! -e /app/cgtlib/private" in text
    assert "assert not b.HAS_PRIVATE_COMPUTE" in text


def test_release_check_tracks_identity_authority_template_keys() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    for marker in (
        '"AUTH_TOKEN_PEPPER"',
        '"AUTH_RATE_LIMIT_PEPPER"',
        '"AUTH_DELIVERY_KEY_RING_JSON"',
        '"AUTH_DELIVERY_CURRENT_KEY_VERSION"',
        '"AUTH_MFA_KEY_RING_JSON"',
        '"AUTH_MFA_CURRENT_KEY_VERSION"',
        '"ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON"',
        '"ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION"',
    ):
        assert marker in text
