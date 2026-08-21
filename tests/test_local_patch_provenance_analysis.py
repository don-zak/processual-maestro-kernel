import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH_ANALYZER = ROOT / "scripts" / "analyze_local_patch_provenance.ps1"


def test_local_patch_provenance_analysis_is_check_only_and_non_destructive() -> None:
    source = PATCH_ANALYZER.read_text(encoding="utf-8")

    assert '"apply", "--check"' in source
    assert '"--reverse"' in source
    assert "ALREADY_REPRESENTED_IN_CURRENT_TREE" in source
    assert "NOT_YET_APPLIED_TO_CURRENT_TREE" in source
    assert "DIVERGED_OR_PARTIALLY_REPRESENTED" in source
    assert "retirement_candidate" in source
    assert "deletion_authorized = $false" in source
    assert "no patch application or deletion authority" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None
    assert re.search(r"(?im)^\s*git\s+apply\s+(?!.*--check)", source) is None
