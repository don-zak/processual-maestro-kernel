from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_package_metadata_does_not_declare_open_source_license():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    project = pyproject["project"]
    assert "license" not in project
    assert "license-files" not in project


def test_source_distribution_manifest_excludes_private_and_operational_content():
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

    required_rules = {
        "prune tests",
        "prune docs",
        "prune scripts",
        "prune data",
        "prune .github",
        "global-exclude .env",
        "global-exclude .env.*",
        "global-exclude *.sqlite",
        "global-exclude *.sqlite3",
        "global-exclude *.db",
        "global-exclude *.jsonl",
        "global-exclude subscriptions.json",
        "global-exclude usage_logs.jsonl",
        "global-exclude settings_*.json",
    }

    assert required_rules.issubset(set(manifest.splitlines()))


def test_only_runtime_packages_are_discovered_for_distribution():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    package_find = pyproject["tool"]["setuptools"]["packages"]["find"]
    assert package_find["include"] == [
        "processual_kernel*",
        "cgtlib*",
        "processual_api*",
    ]
    assert {"tests*", "docs*", "scripts*", "build*", "dist*"}.issubset(
        set(package_find["exclude"])
    )
