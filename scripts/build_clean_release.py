#!/usr/bin/env python3
"""Build a clean release package for Processual Maestro Kernel.

Usage:
    python scripts/build_clean_release.py

Steps:
1. Create a temp clean_build/ directory
2. Copy project files excluding .venv, .env, cache, data artifacts
3. Run release_check.py on clean_build/
4. Create a ZIP archive from clean_build/
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = REPO_ROOT / "clean_build"
RELEASES_DIR = REPO_ROOT / "releases"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".hypothesis",
    ".mypy_cache",
    ".ruff_cache",
    "clean_build",
    "releases",
}

EXCLUDE_FILES = {
    ".env",
    ".coverage",
}

EXCLUDE_SUFFIXES = {
    ".pyc",
    ".pyo",
}

INCLUDE_PATTERNS = {
    ".py",
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".cfg",
    ".ini",
    ".txt",
    ".sh",
    ".ps1",
    ".bat",
    ".gitkeep",
    ".gitignore",
    ".example",
    "Dockerfile",
    ".dockerignore",
    "docker-compose.yml",
}


def _should_include(path: Path, rel: str) -> bool:
    parts = rel.split(os.sep)
    for part in parts:
        if part in EXCLUDE_DIRS:
            return False
    name = path.name
    if name in EXCLUDE_FILES:
        return False
    if any(name.endswith(s) for s in EXCLUDE_SUFFIXES):
        return False
    if path.is_file() and path.suffix == "" and name not in ("Dockerfile",):
        if "." not in name and name not in (".gitkeep", ".gitignore"):
            return False
    return True


def _copy_tree(src: Path, dst: Path) -> list[str]:
    copied: list[str] = []
    for root, dirs, files in os.walk(src):
        rel_root = Path(root).relative_to(src)
        for d in list(dirs):
            if d in EXCLUDE_DIRS:
                dirs.remove(d)
        dst_root = dst / rel_root
        dst_root.mkdir(parents=True, exist_ok=True)
        for f in files:
            src_path = Path(root) / f
            rel = str(rel_root / f) if str(rel_root) != "." else f
            if not _should_include(src_path, rel):
                continue
            dst_path = dst_root / f
            shutil.copy2(src_path, dst_path)
            copied.append(str(rel))
    return copied


def _clean_data_artifacts(build_dir: Path) -> None:
    data_dir = build_dir / "processual_api" / "data"
    if not data_dir.is_dir():
        return
    for entry in data_dir.iterdir():
        if entry.name == ".gitkeep":
            continue
        if entry.is_file():
            entry.unlink()


def _run_release_check(build_dir: Path) -> int:
    script = REPO_ROOT / "scripts" / "release_check.py"
    if not script.is_file():
        print("  WARN  release_check.py not found, skipping")
        return 0
    result = subprocess.run(
        [sys.executable, str(script), "--root", str(build_dir), "--skip-docker", "--skip-pytest"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout + result.stderr
    print(output)
    return result.returncode


def _create_zip(build_dir: Path) -> Path:
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    zip_path = RELEASES_DIR / f"processual_maestro_clean_{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(build_dir):
            for f in files:
                fp = Path(root) / f
                arcname = fp.relative_to(build_dir)
                zf.write(fp, arcname)
    return zip_path


def _save_manifest(build_dir: Path, copied: list[str], zip_path: Path, rc: int) -> None:
    manifest = {
        "build_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": str(REPO_ROOT),
        "build_dir": str(build_dir),
        "zip_archive": str(zip_path),
        "total_files": len(copied),
        "files": sorted(copied),
        "release_check_exit_code": rc,
    }
    manifest_path = RELEASES_DIR / f"{zip_path.stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build a clean release package")
    parser.add_argument("--skip-clean", action="store_true", help="Skip dev artifact cleanup before copy")
    args = parser.parse_args()

    print("=" * 60)
    print("  Processual Maestro — Clean Release Builder")
    print("=" * 60)

    if not args.skip_clean:
        clean_script = REPO_ROOT / "scripts" / "clean_dev_artifacts.py"
        if clean_script.is_file():
            print(f"\n>>> Cleaning development artifacts ...")
            subprocess.run([sys.executable, str(clean_script)], cwd=REPO_ROOT, timeout=120)
        else:
            print(f"  WARN  clean_dev_artifacts.py not found, skipping")

    if BUILD_DIR.exists():
        print(f"\n>>> Removing existing build directory: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)

    print(f"\n>>> Copying files to {BUILD_DIR} ...")
    copied = _copy_tree(REPO_ROOT, BUILD_DIR)
    print(f"  Copied {len(copied)} files")

    print(f">>> Cleaning runtime artifacts from processual_api/data/ ...")
    _clean_data_artifacts(BUILD_DIR)

    print(f"\n>>> Running release_check on {BUILD_DIR} ...")
    rc = _run_release_check(BUILD_DIR)

    if rc != 0:
        print(f"\n  FAIL  release_check returned {rc} — aborting ZIP creation")
        print(f"  Inspect {BUILD_DIR} for issues, fix, and re-run")
        sys.exit(rc)

    print(f"\n>>> Creating ZIP archive ...")
    zip_path = _create_zip(BUILD_DIR)
    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  Created: {zip_path}")
    print(f"  Size:    {zip_size_mb:.2f} MB")

    manifest_path = _save_manifest(BUILD_DIR, copied, zip_path, rc)
    print(f"  Manifest: {manifest_path}")

    print(f"\n>>> Cleaning up build directory ...")
    shutil.rmtree(BUILD_DIR)

    print(f"\n{'=' * 60}")
    print(f"  RESULT: Release package ready")
    print(f"  Path:   {zip_path}")
    print(f"  Files:  {len(copied)}")
    print(f"  Size:   {zip_size_mb:.2f} MB")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
