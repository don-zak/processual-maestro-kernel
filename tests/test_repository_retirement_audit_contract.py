from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_repository_retirement.ps1"
GITIGNORE = ROOT / ".gitignore"


def test_repository_retirement_audit_never_auto_deletes_tracked_files() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "tracked_auto_delete = $false" in source
    assert "Tracked files are never auto-deleted by this audit" in source
    assert "$item.deletion_eligible" in source
    assert "$item.tracked = $false" not in source
    assert "git ls-files" in source
    assert "git status --porcelain=v1 --ignored" in source


def test_repository_retirement_audit_protects_history_and_qualification_surfaces() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "^alembic/versions/" in source
    assert "^tests/" in source
    assert "^docs/" in source
    assert "^qualification/" in source
    assert "^\\.github/workflows/" in source
    assert "COMPATIBILITY_HOLD" in source
    assert "PROTECTED_HISTORY_OR_TEST" in source


def test_repository_retirement_audit_outputs_are_quarantined_from_git() -> None:
    gitignore = GITIGNORE.read_text(encoding="utf-8")

    assert ".pmk-repo-audit/" in gitignore


def test_safe_cleanup_is_limited_to_ignored_untracked_generated_residue() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "$eligible = $isIgnored -and -not (Test-ProtectedPath $path)" in source
    assert "SAFE_LOCAL_RESIDUE" in source
    assert "Remove-Item -LiteralPath $item.path -Recurse -Force" in source
    assert "No tracked file is deleted automatically" in source


def test_markdown_summary_lines_do_not_escape_their_closing_quotes() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert '$lines.Add("- Branch: $branch")' in source
    assert '$lines.Add("- HEAD: $head")' in source
    assert '$lines.Add("- Branch: `$branch`")' not in source
    assert '$lines.Add("- HEAD: `$head`")' not in source
