from __future__ import annotations

from pathlib import Path

from tools.secret_scan import scan_text, scan_tree


def _credential_line(name: str, value: str) -> str:
    return f'{name} = "{value}"'


def _unquoted_credential_line(name: str, value: str) -> str:
    return f"{name}={value}"


def test_secret_scan_detects_private_key_material() -> None:
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    findings = scan_text(f"{marker}\nabc\n-----END " + "PRIVATE KEY-----")
    assert [finding.rule for finding in findings] == ["private_key_material"]


def test_secret_scan_detects_high_confidence_credential_assignment() -> None:
    findings = scan_text(_credential_line("client_" + "secret", "real-credential-value-123456"))
    assert [finding.rule for finding in findings] == ["credential_assignment"]


def test_secret_scan_detects_unquoted_environment_credential() -> None:
    findings = scan_text(_unquoted_credential_line("CLIENT_" + "SECRET", "real-credential-value-123456"))
    assert [finding.rule for finding in findings] == ["credential_assignment"]


def test_secret_scan_ignores_runtime_variable_assignment_that_is_not_a_literal() -> None:
    source = 'api_key = request.headers.get("X-API-Key", "").strip()'
    assert scan_text(source, path="processual_api/middleware/runtime_capacity.py") == []


def test_secret_scan_treats_generic_test_credentials_as_fixtures() -> None:
    source = _credential_line("password", "owner-chosen-password")
    assert scan_text(source, path="tests/test_onboarding.py") == []


def test_secret_scan_keeps_high_confidence_token_detection_in_tests() -> None:
    token = "ghp_" + "A" * 36
    findings = scan_text(f'raw_value = "{token}"', path="tests/test_connector.py")
    assert [finding.rule for finding in findings] == ["github_token"]


def test_secret_scan_allows_documented_placeholders() -> None:
    text = "\n".join(
        (
            _credential_line("client_" + "secret", "replace-me-with-secret"),
            _credential_line("api_" + "key", "${API_KEY}"),
            _credential_line("password", "example-password-value"),
            _credential_line("access_" + "token", "redacted-access-token"),
            _unquoted_credential_line("CLIENT_" + "SECRET", "${CLIENT_SECRET}"),
        )
    )
    assert scan_text(text) == []


def test_secret_scan_allows_explicit_high_confidence_test_fixture_marker() -> None:
    token = "sk-" + "test-only-" + "A" * 32
    assert scan_text(f'raw_secret = "{token}"', path="tests/test_crypto.py") == []


def test_secret_scan_does_not_confuse_private_math_terms_with_credentials() -> None:
    text = "SECRET_WEIGHT=0.913 proprietary_equation=x+y threshold=0.42"
    assert scan_text(text) == []


def test_secret_scan_tree_includes_key_files(tmp_path: Path) -> None:
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    (tmp_path / "fixture.key").write_text(marker, "utf-8")

    findings = scan_tree(tmp_path)
    assert [(finding.path, finding.rule) for finding in findings] == [
        ("fixture.key", "private_key_material")
    ]


def test_secret_scan_tree_skips_build_and_generated_evidence(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / "release-evidence").mkdir()
    (tmp_path / "src" / "safe.py").write_text(_credential_line("api_" + "key", "${API_KEY}"), "utf-8")
    (tmp_path / "build" / "generated.py").write_text(
        _credential_line("password", "real-credential-value-123456"),
        "utf-8",
    )
    (tmp_path / "release-evidence" / "inventory.json").write_text(
        _credential_line("access_" + "token", "real-credential-value-123456"),
        "utf-8",
    )

    assert scan_tree(tmp_path) == []


def test_current_repository_has_no_high_confidence_secret_findings() -> None:
    findings = scan_tree(Path("."))
    assert findings == []
