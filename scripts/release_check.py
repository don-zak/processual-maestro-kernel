#!/usr/bin/env python3
"""Static pre-release validation for Processual Maestro Kernel v2.0.0.

This script validates repository/package hygiene, documented production
configuration, the public Docker artifact boundary, and pytest. Passing this
script is necessary evidence, not an automatic production-readiness verdict.

Exit code 0 = requested static pre-release checks passed.
Exit code 1 = one or more requested checks failed.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_CHECK_IMAGE = "pmk-public-release-check:local"

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
EXEMPT_DIRS = {".git", ".venv"}

REQUIRED_PRODUCTION_TEMPLATE_KEYS = (
    "JWT_SECRET",
    "CORS_ORIGINS",
    "DATABASE_URL",
    "REDIS_URL",
    "POSTGRES_PASSWORD",
    "REDIS_PASSWORD",
    "API_KEYS",
    "PROCESSUAL_CRYPTO_KEY_B64",
    "GRAFANA_ADMIN_PASSWORD",
    "MAESTRO_ADMIN_EMAIL",
    "MAESTRO_ADMIN_PASSWORD",
    "AUTH_TOKEN_PEPPER",
    "AUTH_RATE_LIMIT_PEPPER",
    "AUTH_DELIVERY_KEY_RING_JSON",
    "AUTH_DELIVERY_CURRENT_KEY_VERSION",
    "AUTH_PUBLIC_BASE_URL",
    "AUTH_MFA_KEY_RING_JSON",
    "AUTH_MFA_CURRENT_KEY_VERSION",
    "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_KEY_RING_JSON",
    "ADMIN_MARKETPLACE_PAYMENT_DESTINATION_CURRENT_KEY_VERSION",
)


def _configure_stdio() -> None:
    stdout_buffer = getattr(sys.stdout, "buffer", None)
    stderr_buffer = getattr(sys.stderr, "buffer", None)
    if stdout_buffer is not None:
        sys.stdout = io.TextIOWrapper(stdout_buffer, encoding="utf-8", errors="replace")
    if stderr_buffer is not None:
        sys.stderr = io.TextIOWrapper(stderr_buffer, encoding="utf-8", errors="replace")


def _error(msg: str) -> None:
    print(f"  FAIL  {msg}")


def _ok(msg: str) -> None:
    print(f"  OK    {msg}")


def _warn(msg: str) -> None:
    print(f"  WARN  {msg}")


def check_no_venv(base: Path) -> int:
    if (base / ".venv").is_dir():
        _error("Found .venv directory — exclude it from the release workspace/package")
        return 1
    _ok("No .venv directory found")
    return 0


def check_no_env_file(base: Path) -> int:
    if (base / ".env").is_file():
        _error("Found .env file — it must not ship in a release package")
        return 1
    _ok("No .env file in release workspace")
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
            if any(fname.endswith(pat) or fname == pat for pat in FILE_ARTIFACTS):
                _error(f"Found cache/coverage artifact: {os.path.join(root, fname)}")
                errors += 1
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
        if entry.is_file():
            _error(f"Unexpected/runtime file in data/: {entry.name}")
            errors += 1
    if errors == 0:
        _ok("data/ directory contains only .gitkeep")
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
            if stripped.startswith("#") or not stripped or "=" not in stripped:
                continue
            for pat in WEAK_PATTERNS:
                if pat.search(stripped):
                    _error(f"{fname}:{i} matches weak pattern '{pat.pattern}'")
                    errors += 1
                    break
    if errors == 0:
        _ok("No weak/default secret literals found in checked files")
    return errors


def check_env_production_example_exists(base: Path) -> int:
    path = base / ".env.production.example"
    if not path.is_file():
        _error(".env.production.example is missing")
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [
        key for key in REQUIRED_PRODUCTION_TEMPLATE_KEYS
        if f"{key}=" not in text and f"{key} " not in text
    ]
    if missing:
        _error(f".env.production.example missing required keys: {', '.join(missing)}")
        return 1
    _ok(".env.production.example covers the current production authority contract")
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
    _ok("README.md exists with no blocked placeholder text")
    return 0


def check_docker_public_build() -> int:
    try:
        build = subprocess.run(
            ["docker", "build", "--target", "public", "-t", PUBLIC_CHECK_IMAGE, "."],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if build.returncode != 0:
            _error("docker build --target public failed")
            return 1
        boundary = subprocess.run(
            [
                "docker", "run", "--rm", "--entrypoint", "sh", PUBLIC_CHECK_IMAGE,
                "-c",
                "test ! -e /app/cgtlib/private && python -c \"import cgtlib._backend as b; assert not b.HAS_PRIVATE_COMPUTE\"",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if boundary.returncode != 0:
            _error("public image boundary check failed: private CGT is present or public fallback import is broken")
            return 1
        _ok("Public Docker target builds and excludes private CGT runtime authority")
        return 0
    except FileNotFoundError:
        _warn("Docker not available; Docker evidence remains outstanding")
        return 0
    except subprocess.TimeoutExpired:
        _error("Docker qualification timed out")
        return 1


def _evaluate_pytest_result(returncode: int, output: str) -> int:
    pass_match = re.search(r"(\d+) passed", output)
    fail_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) error", output)
    passed = int(pass_match.group(1)) if pass_match else 0
    failed = int(fail_match.group(1)) if fail_match else 0
    test_errors = int(error_match.group(1)) if error_match else 0
    if passed + failed == 0:
        _error("pytest returned 0 tests")
        return 1
    if returncode != 0 or failed > 0 or test_errors > 0:
        _error(f"pytest failed: exit={returncode}, failed={failed}, errors={test_errors}")
        return 1
    _ok(f"pytest: {passed} passed")
    return 0


def run_pytest() -> int:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=short", "-q"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=600,
        )
        return _evaluate_pytest_result(result.returncode, result.stdout + result.stderr)
    except FileNotFoundError:
        _error("pytest not found")
        return 1
    except subprocess.TimeoutExpired:
        _error("pytest timed out after 600 seconds")
        return 1


def main() -> NoReturn:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="Static pre-release validation for Processual Maestro Kernel")
    parser.add_argument("--root", type=str, default=None)
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
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
        print("RESULT: STATIC PRE-RELEASE CHECKS PASS — operator/runtime qualification is still required")
        sys.exit(0)
    print(f"RESULT: {total_errors} check(s) FAILED — fix before release qualification")
    sys.exit(1)


if __name__ == "__main__":
    main()
