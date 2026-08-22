import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance" / "repository_retirement_quarantine.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _tracked_paths() -> set[str]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def test_local_tooling_quarantine_policy_is_fail_closed():
    quarantine = _manifest()["local_tooling_quarantine"]

    assert quarantine["repository_tracking_forbidden"] is True
    assert quarantine["force_add_is_not_authorized"] is True
    assert quarantine["canonical_local_only"]
    assert quarantine["retired_exact_paths"]


def test_retired_local_tools_cannot_reenter_git_authority():
    quarantine = _manifest()["local_tooling_quarantine"]
    tracked = _tracked_paths()

    assert not (set(quarantine["retired_exact_paths"]) & tracked)


def test_canonical_local_operator_tools_remain_local_only():
    quarantine = _manifest()["local_tooling_quarantine"]
    tracked = _tracked_paths()

    assert not (set(quarantine["canonical_local_only"]) & tracked)


def test_retired_and_canonical_local_tool_lists_do_not_overlap():
    quarantine = _manifest()["local_tooling_quarantine"]

    retired = set(quarantine["retired_exact_paths"])
    canonical = set(quarantine["canonical_local_only"])
    assert retired.isdisjoint(canonical)
