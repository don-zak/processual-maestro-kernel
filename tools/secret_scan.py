from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


_TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".key",
    ".md",
    ".pem",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "release-evidence",
}
_PLACEHOLDER_MARKERS = (
    "${",
    "{{",
    "<",
    "changeme",
    "do-not-store-plain",
    "dummy",
    "example",
    "fake",
    "fixture",
    "local_test",
    "not-a-secret",
    "placeholder",
    "redacted",
    "replace-me",
    "sample",
    "test-only",
    "unit-test",
)
_TEST_FIXTURE_LINE_MARKERS = (
    "raw_secret",
    "fixture_secret",
    "test_secret",
    "fake_secret",
    "dummy_secret",
    "without-crypto",
)
_CREDENTIAL_NAME = r"(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|password)"


@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: str
    line: int
    rule: str


_PRIVATE_KEY_RULE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_QUOTED_CREDENTIAL_ASSIGNMENT_RULE = re.compile(
    rf"(?i)^\s*{_CREDENTIAL_NAME}\s*(?:=|:)\s*[\"']([^\"']{{12,}})[\"']\s*(?:#.*)?$"
)
_ENV_CREDENTIAL_ASSIGNMENT_RULE = re.compile(
    rf"(?i)^\s*(?:export\s+)?{_CREDENTIAL_NAME}\s*=\s*([A-Za-z0-9_./:+@%\-]{{12,}})\s*(?:#.*)?$"
)
_HIGH_CONFIDENCE_TOKEN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
)


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized.startswith("tests/") or "/tests/" in f"/{normalized}"


def _is_explicit_test_fixture_line(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in _TEST_FIXTURE_LINE_MARKERS)


def _candidate_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        if path.name.startswith(".env") or path.suffix.lower() in _TEXT_SUFFIXES:
            candidates.append(path)
    return candidates


def scan_text(text: str, *, path: str = "<memory>") -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    test_path = _is_test_path(path)
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _PRIVATE_KEY_RULE.search(line):
            findings.append(SecretFinding(path=path, line=line_number, rule="private_key_material"))

        if not test_path:
            assignment = _QUOTED_CREDENTIAL_ASSIGNMENT_RULE.search(line)
            if assignment is None:
                assignment = _ENV_CREDENTIAL_ASSIGNMENT_RULE.search(line)
            if assignment:
                value = assignment.group(1)
                if not _is_placeholder(value):
                    findings.append(SecretFinding(path=path, line=line_number, rule="credential_assignment"))

        for rule_name, pattern in _HIGH_CONFIDENCE_TOKEN_RULES:
            match = pattern.search(line)
            if not match or _is_placeholder(match.group(0)):
                continue
            if test_path and _is_explicit_test_fixture_line(line):
                continue
            findings.append(SecretFinding(path=path, line=line_number, rule=rule_name))
    return findings


def scan_tree(root: Path) -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for path in _candidate_files(root):
        try:
            text = path.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        findings.extend(scan_text(text, path=relative))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan source/package inputs for high-confidence credential material.")
    parser.add_argument("root", nargs="?", default=".", help="Repository root to scan")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    findings = scan_tree(root)
    if not findings:
        print("secret-scan: no high-confidence findings")
        return 0

    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.rule}")
    print(f"secret-scan: {len(findings)} high-confidence finding(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
