from __future__ import annotations

import tomllib
from pathlib import Path


def test_reference_scenarios_json_is_declared_as_package_data() -> None:
    config = tomllib.loads(Path("pyproject.toml").read_text("utf-8"))

    package_data = config["tool"]["setuptools"]["package-data"]

    assert package_data["cgtlib.data"] == ["reference_scenarios.json"]
