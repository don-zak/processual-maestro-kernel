from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "dependency_census.py"


def _run(fmt: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(REPO_ROOT), "--format", fmt],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def test_dependency_census_json_schema_and_current_packages() -> None:
    payload = json.loads(_run("json"))

    assert payload["schema_version"] == 1
    assert list(payload["packages"]) == ["cgtlib", "processual_api", "processual_kernel"] or set(payload["packages"]) == {
        "processual_kernel",
        "cgtlib",
        "processual_api",
    }
    assert payload["totals"]["python_files"] > 0
    assert payload["totals"]["python_bytes"] > 0

    for package in ("processual_kernel", "cgtlib", "processual_api"):
        assert payload["packages"][package]["python_files"] > 0
        assert payload["packages"][package]["python_bytes"] > 0


def test_dependency_census_output_is_deterministic() -> None:
    assert _run("json") == _run("json")
    assert _run("markdown") == _run("markdown")


def test_dependency_census_reports_no_reverse_api_edge_from_core_packages() -> None:
    payload = json.loads(_run("json"))
    reverse_edges = {
        (edge["from"], edge["to"])
        for edge in payload["internal_edges"]
        if edge["to"] == "processual_api"
    }

    assert ("processual_kernel", "processual_api") not in reverse_edges
    assert ("cgtlib", "processual_api") not in reverse_edges
