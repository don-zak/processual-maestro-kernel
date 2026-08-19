from __future__ import annotations

from pathlib import Path

from tools.secret_scan import scan_text, scan_tree


def test_secret_scan_detects_private_key_material() -> None:
    findings = scan_text("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----")
    assert [finding.rule for finding in findings] == ["private_key_material"]


def test_secret_scan_detects_high_confidence_credential_assignment() -> None:
    findings = scan_text('client_secret = "real-secret-value-123456"')
    assert [finding.rule for finding in findings] == ["credential_assignment"]


def test_secret_scan_allows_documented_placeholders() -> None:
    text = "\n".join(
        (
            'client_secret = "replace-me-with-secret"',
            'api_key = "${API_KEY}"',
            'password = "example-password-value"',
            'access_token = "redacted-access-token"',
        )
    )
    assert scan_text(text) == []


def test_secret_scan_does_not_confuse_private_math_terms_with_credentials() -> None:
    text = "SECRET_WEIGHT=0.913 proprietary_equation=x+y threshold=0.42"
    assert scan_text(text) == []


def test_secret_scan_tree_skips_build_and_generated_evidence(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "release-evidence").mkdir()
    (tmp_path / "src" / "safe.py").write_text('api_key = "${API_KEY}"', "utf-8")
    (tmp_path / "build" / "generated.py").write_text('password = "real-secret-value-123456"', "utf-8")
    (tmp_path / "release-evidence" / "inventory.json").write_text(
        '{"access_token": "real-secret-value-123456"}',
        "utf-8",
    )

    assert scan_tree(tmp_path) == []


def test_current_repository_has_no_high_confidence_secret_findings() -> None:
    findings = scan_tree(Path("."))
    assert findings == []
