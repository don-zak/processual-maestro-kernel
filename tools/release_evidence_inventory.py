from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "pmk-release-evidence-inventory-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_sha() -> str:
    configured = os.environ.get("GITHUB_SHA", "").strip()
    if configured:
        return configured

    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _installed_packages() -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for distribution in metadata.distributions():
        package_metadata = distribution.metadata
        name = package_metadata.get("Name") or distribution.name
        packages.append(
            {
                "name": str(name),
                "version": distribution.version,
                "license_expression": package_metadata.get("License-Expression"),
                "license": package_metadata.get("License"),
            }
        )

    packages.sort(key=lambda item: (item["name"].lower(), item["version"]))
    return packages


def build_inventory(dist_dir: Path) -> dict[str, Any]:
    artifacts = [
        {
            "filename": path.name,
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(dist_dir.iterdir())
        if path.is_file()
    ]
    if not artifacts:
        raise ValueError(f"No release artifacts found in {dist_dir}.")

    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha": _source_sha(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
        "artifacts": artifacts,
        "installed_packages": _installed_packages(),
        "inventory_scope": (
            "release-gate installed environment plus built distribution artifacts; "
            "this is dependency/license evidence, not a CycloneDX/SPDX SBOM"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist-dir", default="dist")
    parser.add_argument("--output", default="release-evidence/release-inventory.json")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory(Path(args.dist_dir))
    output_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
