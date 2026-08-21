import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "audit_repository_retirement.ps1"
SUPERSESSION = ROOT / "scripts" / "analyze_local_tooling_supersession.ps1"
RETIREMENT_EVIDENCE = ROOT / "scripts" / "extract_local_tooling_retirement_evidence.ps1"
SEMANTIC_REPLACEMENT = ROOT / "scripts" / "analyze_legacy_function_semantic_replacement.ps1"
REPORTING_ONLY = ROOT / "scripts" / "analyze_legacy_reporting_only_retirement.ps1"
OUTPUT_CONSUMERS = ROOT / "scripts" / "analyze_legacy_report_output_consumers.ps1"
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


def test_local_tooling_families_are_summarized_without_authorizing_deletion() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "Get-LocalToolingMetadata" in source
    assert "Invoke-PMKRepoAudit" in source
    assert "Retire-Safe-CGT17Branches" in source
    assert "local_tooling_families" in source
    assert "latest_numeric_version_by_name" in source
    assert "fixed_variant_paths" in source
    assert "deletion_authorized = $false" in source
    assert "tooling_version_order_is_not_deletion_authority = $true" in source
    assert "Tool version ordering is inventory evidence only" in source


def test_local_tooling_is_fingerprinted_and_exact_duplicates_are_grouped() -> None:
    source = AUDIT.read_text(encoding="utf-8")

    assert "Get-LocalFileFingerprint" in source
    assert "Get-FileHash -LiteralPath $Path -Algorithm SHA256" in source
    assert "sha256 =" in source
    assert "size_bytes =" in source
    assert "line_count =" in source
    assert "exact_duplicate_groups" in source
    assert "Group-Object sha256" in source
    assert "local_tooling_content_fingerprinted = $true" in source
    assert "exact_duplicate_hash_requires_canonical_retained_copy = $true" in source
    assert "Exact duplicate hashes are equivalence evidence" in source


def test_structural_supersession_analysis_is_non_destructive_and_explicit() -> None:
    source = SUPERSESSION.read_text(encoding="utf-8")

    assert "normalized_sha256" in source
    assert "function_count" in source
    assert "functions =" in source
    assert "parameter_count" in source
    assert "parameters =" in source
    assert "latest_contains_all_candidate_functions" in source
    assert "latest_contains_all_candidate_parameters" in source
    assert "missing_functions_in_latest" in source
    assert "missing_parameters_in_latest" in source
    assert "normalized_duplicate_groups" in source
    assert "deletion_authorized = $false" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None


def test_behavioral_supersession_analysis_tracks_operational_primitives() -> None:
    source = SUPERSESSION.read_text(encoding="utf-8")

    assert "Get-BehavioralSignature" in source
    assert "git_commands" in source
    assert "gh_commands" in source
    assert "pytest_commands" in source
    assert "file_writes" in source
    assert "file_deletes" in source
    assert "network_calls" in source
    assert "process_calls" in source
    assert "latest_contains_all_candidate_behavioral_signals" in source
    assert "missing_git_commands_in_latest" in source
    assert "missing_gh_commands_in_latest" in source
    assert "missing_file_write_primitives_in_latest" in source
    assert "missing_file_delete_primitives_in_latest" in source
    assert "local structural, behavioral, operational-reference, and call-site comparison only; no deletion authority" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None


def test_tooling_retirement_requires_reference_and_call_site_evidence() -> None:
    source = SUPERSESSION.read_text(encoding="utf-8")

    assert "Get-TrackedReferenceEvidence" in source
    assert "Get-LocalToolingReferenceEvidence" in source
    assert "Get-FunctionCallEvidence" in source
    assert "tracked_reference_count" in source
    assert "local_tooling_reference_count" in source
    assert "reference_free_in_repository_and_local_tooling" in source
    assert "missing_function_call_evidence" in source
    assert "missing_functions_are_uncalled_in_candidate" in source
    assert "retirement_evidence_complete" in source
    assert "deletion_authorized = $false" in source


def test_retirement_reference_evidence_excludes_audit_self_references() -> None:
    source = SUPERSESSION.read_text(encoding="utf-8")

    assert "referenceExclusions" in source
    assert ":!scripts/audit_repository_retirement.ps1" in source
    assert ":!scripts/analyze_local_tooling_supersession.ps1" in source
    assert ":!scripts/extract_local_tooling_retirement_evidence.ps1" in source
    assert ":!tests/**" in source
    assert ":!docs/**" in source
    assert ":!qualification/**" in source
    assert "operational-reference" in source


def test_focused_retirement_evidence_extractor_is_non_destructive_and_targeted() -> None:
    source = RETIREMENT_EVIDENCE.read_text(encoding="utf-8")

    assert "Get-FunctionEvidence" in source
    assert "missing_function_implementations" in source
    assert "missing_function_implementation_groups" in source
    assert "body_sha256" in source
    assert "body_preview" in source
    assert "retire_safe_fixed_reference" in source
    assert "tracked_reference_samples" in source
    assert "focused local evidence extraction only; no deletion authority" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None


def test_focused_retirement_evidence_extracts_function_bodies_by_brace_depth() -> None:
    source = RETIREMENT_EVIDENCE.read_text(encoding="utf-8")

    assert "$depth = 0" in source
    assert "$seenOpeningBrace = $false" in source
    assert "if ($ch -eq '{')" in source
    assert "elseif ($ch -eq '}')" in source
    assert "if ($seenOpeningBrace -and $depth -eq 0) { break }" in source


def test_legacy_function_semantic_replacement_analysis_is_ast_based_and_non_destructive() -> None:
    source = SEMANTIC_REPLACEMENT.read_text(encoding="utf-8")

    assert "System.Management.Automation.Language.Parser" in source
    assert "FunctionDefinitionAst" in source
    assert "CommandAst" in source
    assert "StringConstantExpressionAst" in source
    assert "missing_commands_in_canonical" in source
    assert "missing_literals_in_canonical" in source
    assert "semantic_replacement_proven" in source
    assert "deletion_authorized = $false" in source
    assert "local AST semantic comparison only; no deletion authority" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None


def test_reporting_only_retirement_analysis_is_ast_based_and_non_destructive() -> None:
    source = REPORTING_ONLY.read_text(encoding="utf-8")

    assert "System.Management.Automation.Language.Parser" in source
    assert "FunctionDefinitionAst" in source
    assert "ReturnStatementAst" in source
    assert "mutatingCommands" in source
    assert "reporting_only_candidate" in source
    assert "any_result_captured" in source
    assert "retirement_safe_if_parent_script_unreferenced" in source
    assert "all_missing_functions_reporting_only" in source
    assert "deletion_authorized = $false" in source
    assert "local reporting-only role analysis; no deletion authority" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None


def test_legacy_report_output_consumer_analysis_is_ast_based_and_non_destructive() -> None:
    source = OUTPUT_CONSUMERS.read_text(encoding="utf-8")

    assert "System.Management.Automation.Language.Parser" in source
    assert "FunctionDefinitionAst" in source
    assert "Set-Content" in source
    assert "candidate_output_names" in source
    assert "tracked_consumer_count" in source
    assert "output_unconsumed_by_tracked_runtime" in source
    assert "retirement_output_consumer_evidence_complete" in source
    assert "referenceExclusions" in source
    assert "deletion_authorized = $false" in source
    assert "local legacy report output consumer analysis only; no deletion authority" in source
    assert re.search(r"(?im)^\s*Remove-Item\b", source) is None


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
