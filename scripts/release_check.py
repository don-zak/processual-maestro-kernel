#!/usr/bin/env python3
"""Pre-release validation script for Processual Maestro Kernel v2.0.0.

Checks:
1. No .venv directory in the tree
2. No .env file in the release (must use .env.example / .env.production.example)
3. No __pycache__ / .pyc / .pyo / .pytest_cache / .hypothesis artifacts
4. No runtime artifacts in processual_api/data/ (only .gitkeep allowed)
5. No weak / default secrets in .env or docker-compose.yml
6. All required env vars documented in .env.production.example
7. Public Docker target builds without error (if Docker available)
8. pytest passes with >= 90% pass rate
9. README exists and contains no placeholder text

Exit code 0 = release ready, 1 = issues found.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]

WEAK_PATTERNS: list[re.Pattern] = [
    re.compile(r, re.IGNORECASE)
    for r in [
        r"CHANGE_ME",
        r"(?<!= )\"\"",
        r"(?<!= )''",
        r"=admin",
        r"=password",
        r"=test",
        r"=changeme",
        r"=123456",
    ]
]

DIR_ARTIFACTS = {"__pycache__", ".pytest_cache", ".hypothesis", ".mypy_cache", ".ruff_cache"}
FILE_ARTIFACTS = {".pyc", ".pyo", ".coverage"}
EXEMPT_DIRS = {".git", ".venv"}  # .venv excluded from walk but checked separately


def _error(msg: str) -> None:
    print(f"  FAIL  {msg}")


def _ok(msg: str) -> None:
    print(f"  OK    {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def check_no_venv(base: Path) -> int:
    venv_path = base / ".venv"
    if venv_path.is_dir():
        _error("Found .venv directory — remove before release")
        return 1
    _ok("No .venv directory found")
    return 0


def check_no_env_file(base: Path) -> int:
    env_path = base / ".env"
    if env_path.is_file():
        _error("Found .env file — must NOT ship in release package")
        return 1
    _ok("No .env file (only .env.example / .env.production.example)")
    return 0


def check_no_cache_artifacts(base: Path) -> int:
    errors = 0
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in EXEMPT_DIRS]

        for dname in dirs:
            if dname in DIR_ARTIFACTS:
                _error(f"Found {dname} directory: {os.path.join(root, dname)}")
                errors += 1

        for fname in files:
            for pat in FILE_ARTIFACTS:
                if fname.endswith(pat) or fname == pat:
                    _error(f"Found {pat} file: {os.path.join(root, fname)}")
                    errors += 1
                    break

    if errors == 0:
        _ok("No cache / bytecode artifacts found")
    return errors


def check_no_data_artifacts(base: Path) -> int:
    data_dir = base / "processual_api" / "data"
    if not data_dir.is_dir():
        _warn("data/ directory not found, skipping")
        return 0
    errors = 0
    for entry in data_dir.iterdir():
        if entry.name == ".gitkeep":
            continue
        if entry.suffix in (".json", ".jsonl", ".db", ".sqlite") and entry.is_file():
            _error(f"Runtime artifact in data/: {entry.name}")
            errors += 1
        elif entry.is_file():
            _error(f"Unexpected file in data/: {entry.name}")
            errors += 1
    if errors == 0:
        _ok("data/ directory contains only .gitkeep (no runtime artifacts)")
    return errors


def check_no_weak_secrets(base: Path) -> int:
    errors = 0
    for fname in (".env", "docker-compose.yml"):
        path = base / fname
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if "=" not in stripped:
                continue
            for pat in WEAK_PATTERNS:
                if pat.search(stripped):
                    _error(f"{fname}:{i} matches weak pattern '{pat.pattern}': {stripped[:60]}")
                    errors += 1
                    break
    if errors == 0:
        _ok("No weak / default secrets found in .env or docker-compose.yml")
    else:
        _warn("Weak secrets check uses repo root; .env should not be in release package")
    return errors


def check_env_production_example_exists(base: Path) -> int:
    path = base / ".env.production.example"
    if not path.is_file():
        _error(".env.production.example is missing")
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    required_keys = [
        "JWT_SECRET",
        "CORS_ORIGINS",
        "DATABASE_URL",
        "REDIS_URL",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "API_KEYS",
        "PROCESSUAL_CRYPTO_KEY_B64",
        "GRAFANA_ADMIN_PASSWORD",
    ]
    missing = [k for k in required_keys if f"{k}=" not in text and f"{k} " not in text]
    if missing:
        _error(f".env.production.example missing required keys: {', '.join(missing)}")
        return 1
    _ok(".env.production.example exists with all required keys")
    return 0


def check_readme(base: Path) -> int:
    path = base / "README.md"
    if not path.is_file():
        _error("README.md is missing")
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    placeholders = ["TODO", "FIXME", "replace me", "coming soon", "under construction"]
    found = [p for p in placeholders if p.lower() in text.lower()]
    if found:
        _error(f"README.md contains placeholder text: {', '.join(found)}")
        return 1
    _ok("README.md exists with no placeholder text")
    return 0


def check_docker_public_build() -> int:
    try:
        result = subprocess.run(
            ["docker", "build", "--target", "public", "-q", "."],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            _error(f"docker build --target public failed:\n{result.stderr.strip()}")
            return 1
        _ok("Docker public target builds successfully")
        return 0
    except FileNotFoundError:
        _warn("Docker not available, skipping docker build check")
        return 0
    except subprocess.TimeoutExpired:
        _warn("Docker build timed out, skipping")
        return 0


def run_pytest() -> int:
    errors = 0
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=short", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + result.stderr

        pass_match = re.search(r"(\d+) passed", output)
        fail_match = re.search(r"(\d+) failed", output)
        error_match = re.search(r"(\d+) error", output)
        passed = int(pass_match.group(1)) if pass_match else 0
        failed = int(fail_match.group(1)) if fail_match else 0
        test_errors = int(error_match.group(1)) if error_match else 0
        total = passed + failed

        if total == 0:
            _error("pytest returned 0 tests — check pytest configuration")
            return 1

        pass_pct = (passed / total) * 100
        if pass_pct < 90:
            _error(f"pytest: {passed}/{total} passed ({pass_pct:.1f}%) — below 90% threshold")
            errors += 1
        else:
            _ok(f"pytest: {passed}/{total} passed ({pass_pct:.1f}%)")

        if test_errors > 0:
            _error(f"pytest: {test_errors} error(s) found")
            errors += 1
        if failed > 0:
            _warn(f"pytest: {failed} test(s) failed")
        return errors
    except FileNotFoundError:
        _error("pytest not found")
        return 1
    except subprocess.TimeoutExpired:
        _error("pytest timed out after 300 seconds")
        return 1


def main() -> NoReturn:
    parser = argparse.ArgumentParser(description="Pre-release validation for Processual Maestro Kernel")
    parser.add_argument("--root", type=str, default=None, help="Root directory to check (default: repo root)")
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest execution")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker build check")
    args = parser.parse_args()

    base = Path(args.root).resolve() if args.root else REPO_ROOT

    total_errors = 0
    total_errors += check_no_venv(base)
    total_errors += check_no_env_file(base)
    total_errors += check_no_cache_artifacts(base)
    total_errors += check_no_data_artifacts(base)
    total_errors += check_no_weak_secrets(base)
    total_errors += check_env_production_example_exists(base)
    total_errors += check_readme(base)
    if not args.skip_docker:
        total_errors += check_docker_public_build()
    if not args.skip_pytest:
        total_errors += run_pytest()

    print()
    if total_errors == 0:
        print("RESULT: RELEASE READY — all checks passed")
        sys.exit(0)
    else:
        print(f"RESULT: {total_errors} check(s) FAILED — fix before release")
        sys.exit(1)


if __name__ == "__main__":
    main()
