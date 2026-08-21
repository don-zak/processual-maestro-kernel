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


def test_cgtlib_reference_data_is_not_hidden_by_generic_data_ignore() -> None:
    gitignore = GITIGNORE.read_text(encoding="utf-8")

    assert "data/" in gitignore
    assert "!cgtlib/data/" in gitignore
    assert "!cgtlib/data/**" in gitignore


def test_safe_cleanup_is_limited_to_generated_non_evidence_non_tooling_residue() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "$eligible = $isGeneratedResidue -and -not $isEvidence -and -not $isTooling -and -not $isProtected" in source
    assert "SAFE_LOCAL_RESIDUE" in source
    assert "Remove-Item -LiteralPath $item.path -Recurse -Force" in source
    assert "No tracked file is deleted automatically" in source


def test_local_qualification_evidence_is_never_auto_deleted() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "localEvidencePatterns" in source
    assert "^\\.pmk-validation/" in source
    assert "^\\.pmk-local-review(?:/|\\.sqlite3$)" in source
    assert "^\\.coverage$" in source
    assert "^coverage\\.xml$" in source
    assert "^pytest-.*\\.log$" in source
    assert "^pmk-review-decisions-v\\d+\\.json$" in source
    assert "^cgt17_branch_retirement_audit_\\d+\\.json$" in source
    assert "^PMK_Transition_Handoff_Report_.*\\.docx$" in source
    assert "^wave.*\\.patch$" in source
    assert "^maestro-update-backup/" in source
    assert "LOCAL_EVIDENCE_HOLD" in source
    assert "local_qualification_evidence_preserved = $true" in source


def test_local_tooling_is_inventoried_but_never_auto_deleted() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "localToolingPatterns" in source
    assert "^Invoke-PMKRepoAudit-.*\\.ps1$" in source
    assert "^Retire-Safe-CGT17Branches.*\\.ps1$" in source
    assert "^crm_eval_sandbox\\.py$" in source
    assert "^verify_local_password\\.py$" in source
    assert "LOCAL_TOOLING_REVIEW" in source
    assert "local_tooling_requires_manual_review = $true" in source


def test_all_untracked_and_ignored_artifacts_are_inventoried() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "if (-not $isGeneratedResidue) { continue }" not in source
    assert "all_local_untracked_and_ignored_artifacts_are_inventoried = $true" in source
    assert "$localArtifacts.Add" in source
    assert "Local artifacts:" in source


def test_python_packaging_residue_is_detected() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "\\.egg-info" in source


def test_audit_infrastructure_is_excluded_from_retirement_candidates() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "auditInfrastructurePatterns" in source
    assert "^scripts/audit_repository_retirement\\.ps1$" in source
    assert "^governance/repository_retirement_quarantine\\.json$" in source
    assert "^\\.pmk-repo-audit/" in source
    assert "if (Test-AuditInfrastructurePath $path) { continue }" in source
    assert "audit_infrastructure_excluded_from_candidates = $true" in source


def test_markdown_summary_lines_do_not_escape_their_closing_quotes() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert '$lines.Add("- Branch: $branch")' in source
    assert '$lines.Add("- HEAD: $head")' in source
    assert '$lines.Add("- Branch: `$branch`")' not in source
    assert '$lines.Add("- HEAD: `$head`")' not in source
