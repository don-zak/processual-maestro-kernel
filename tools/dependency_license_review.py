from __future__ import annotations

import argparse
import json
from importlib import metadata
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "pmk-dependency-license-review-v1"
_LICENSE_CLASSIFIER_PREFIX = "License ::"


def _license_classifiers(package_metadata: metadata.PackageMetadata) -> list[str]:
    classifiers = package_metadata.get_all("Classifier") or []
    return sorted(
        item.strip()
        for item in classifiers
        if item.strip().startswith(_LICENSE_CLASSIFIER_PREFIX)
    )


def build_dependency_license_review() -> dict[str, Any]:
    packages: list[dict[str, Any]] = []
    missing_metadata: list[str] = []

    for distribution in metadata.distributions():
        package_metadata = distribution.metadata
        name = str(package_metadata.get("Name") or distribution.name)
        expression = (package_metadata.get("License-Expression") or "").strip()
        license_text = (package_metadata.get("License") or "").strip()
        classifiers = _license_classifiers(package_metadata)
        declared = bool(expression or license_text or classifiers)
        if not declared:
            missing_metadata.append(name)

        packages.append(
            {
                "name": name,
                "version": distribution.version,
                "license_expression": expression or None,
                "license": license_text or None,
                "license_classifiers": classifiers,
                "metadata_declared": declared,
            }
        )

    packages.sort(key=lambda item: (item["name"].lower(), item["version"]))
    missing_metadata.sort(key=str.lower)
    return {
        "schema_version": SCHEMA_VERSION,
        "packages": packages,
        "summary": {
            "package_count": len(packages),
            "packages_with_license_metadata": len(packages) - len(missing_metadata),
            "packages_missing_license_metadata": len(missing_metadata),
        },
        "missing_license_metadata": missing_metadata,
        "review_scope": (
            "Installed release-qualification environment metadata inventory. "
            "This identifies declared or missing package license metadata; "
            "it does not make a legal compatibility determination."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="release-evidence/dependency-license-review.json",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_dependency_license_review(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
