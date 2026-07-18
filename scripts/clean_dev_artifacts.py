#!/usr/bin/env python3
"""Clean all development artifacts from the working tree.

Removes (dry-run with --dry-run):
  - __pycache__ directories
  - .pyc / .pyo files
  - .pytest_cache / .hypothesis / .mypy_cache / .ruff_cache
  - processual_api/data/* (keeps .gitkeep)
  - releases/ directory
  - clean_build/ directory
  - docs/reports/ directory
  - pytest_clean.txt (root)

Does NOT touch:
  - .venv / venv
  - .env
  - .git
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DIR_ARTIFACTS = {"__pycache__", ".pytest_cache", ".hypothesis", ".mypy_cache", ".ruff_cache"}
FILE_ARTIFACTS = {".pyc", ".pyo"}

EXEMPT_DIRS = {".git", ".venv", "venv"}

PROTECTED_PATHS = {
    REPO_ROOT / ".venv",
    REPO_ROOT / "venv",
    REPO_ROOT / ".env",
    REPO_ROOT / ".git",
}

DATA_DIR = REPO_ROOT / "processual_api" / "data"


def _is_protected(path: Path) -> bool:
    return any(p == path or p in path.parents for p in PROTECTED_PATHS)


def _rm(path: Path, dry_run: bool) -> None:
    if _is_protected(path):
        return
    if not path.exists():
        return
    if dry_run:
        print(f"  would remove: {path.relative_to(REPO_ROOT)}")
        return
    if path.is_dir():
        shutil.rmtree(path)
        print(f"  removed dir:  {path.relative_to(REPO_ROOT)}")
    else:
        path.unlink()
        print(f"  removed file: {path.relative_to(REPO_ROOT)}")


def clean_data(dry_run: bool) -> int:
    if not DATA_DIR.is_dir():
        return 0
    count = 0
    for entry in DATA_DIR.iterdir():
        if entry.name == ".gitkeep":
            continue
        _rm(entry, dry_run)
        count += 1
    if count == 0 and not dry_run:
        print("  OK    data/ already clean")
    return count


def clean_cache_artifacts(dry_run: bool) -> int:
    count = 0
    for root_str, dirs, files in os.walk(REPO_ROOT):
        root = Path(root_str)
        if any(ex in root.parents or root == ex for ex in PROTECTED_PATHS):
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in EXEMPT_DIRS]

        for d in list(dirs):
            if d in DIR_ARTIFACTS:
                _rm(root / d, dry_run)
                dirs.remove(d)
                count += 1

        for f in files:
            for pat in FILE_ARTIFACTS:
                if f.endswith(pat) or f == pat:
                    _rm(root / f, dry_run)
                    count += 1
                    break
    return count


def clean_dirs(dry_run: bool) -> int:
    dirs = [
        REPO_ROOT / "releases",
        REPO_ROOT / "clean_build",
        REPO_ROOT / "docs" / "reports",
    ]
    count = 0
    for d in dirs:
        if d.is_dir():
            _rm(d, dry_run)
            count += 1
    return count


def clean_root_files(dry_run: bool) -> int:
    count = 0
    for f in ("pytest_clean.txt", "pytest_result.txt", "pytest_result_utf8.txt"):
        p = REPO_ROOT / f
        if p.is_file():
            _rm(p, dry_run)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean all development artifacts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without removing")
    args = parser.parse_args()

    label = " (dry-run)" if args.dry_run else ""
    print(f"Cleaning development artifacts{label} ...")

    c1 = clean_data(args.dry_run)
    c2 = clean_cache_artifacts(args.dry_run)
    c3 = clean_dirs(args.dry_run)
    c4 = clean_root_files(args.dry_run)

    print(f"\nRemoved:{label}")
    print(f"  data/ entries:       {c1}")
    print(f"  cache/bytecode:      {c2}")
    print(f"  build dirs:          {c3}")
    print(f"  root report files:   {c4}")

    if args.dry_run:
        print("\nRun without --dry-run to apply.")
    else:
        print("\nDevelopment tree clean.")


if __name__ == "__main__":
    main()
