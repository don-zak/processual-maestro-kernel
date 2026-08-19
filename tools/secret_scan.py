from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".md",
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
    "dummy",
    "example",
    "fake",
    "not-a-secret",
    "placeholder",
    "redacted",
    "replace-me",
    "test-only",
)


@dataclass(frozen=True, slots=True)
class SecretFinding:
    path: str
    line: int
    rule: str


_PRIVATE_KEY_RULE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_CREDENTIAL_ASSIGNMENT_RULE = re.compile(
    r"(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token|refresh[_-]?token|password)\b"
    r"\s*(?:=|:)\s*[\"']([^\"']{12,})[\"']"
)
_HIGH_CONFIDENCE_TOKEN_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
)


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def _candidate_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_PARTS for part in path.parts):
            continue
        if path.name.startswith(".env") or path.suffix.lower() in _TEXT_SUFFIXES:
            yield path


def scan_text(text: str, *, path: str = "<memory>") -> list[SecretFinding]:
    findings: list[SecretFinding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if _PRIVATE_KEY_RULE.search(line):
            findings.append(SecretFinding(path=path, line=line_number, rule="private_key_material"))

        assignment = _CREDENTIAL_ASSIGNMENT_RULE.search(line)
        if assignment and not _is_placeholder(assignment.group(1)):
            findings.append(SecretFinding(path=path, line=line_number, rule="credential_assignment"))

        for rule_name, pattern in _HIGH_CONFIDENCE_TOKEN_RULES:
            match = pattern.search(line)
            if match and not _is_placeholder(match.group(0)):
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
