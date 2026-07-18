from pathlib import Path

DOC_PATH = Path("docs/reports/MAESTRO_CLIENT_SUPERVISOR_CONTENT_MAP.md")


def _read_doc() -> str:
    return DOC_PATH.read_text(encoding="utf-8")


def _assert_contains_all(content: str, markers: tuple[str, ...]) -> None:
    missing = [marker for marker in markers if marker not in content]
    assert not missing, f"Missing content map markers: {missing}"


def test_client_supervisor_content_map_document_exists() -> None:
    assert DOC_PATH.exists()


def test_client_content_map_sections_are_documented() -> None:
    content = _read_doc()

    _assert_contains_all(
        content,
        (
            "Identity",
            "Plan & Usage",
            "API Keys",
            "Provider Connections",
            "Usage & Quotas",
            "Requests / Billing",
            "Support",
        ),
    )


def test_supervisor_content_map_sections_are_documented() -> None:
    content = _read_doc()

    _assert_contains_all(
        content,
        (
            "Client Overview",
            "API Key Supervision",
            "Usage Ledger Review",
            "Quota & Plan Control",
            "Support Intelligence",
            "Enterprise Follow-up",
        ),
    )


def test_usage_summary_and_ledger_sources_are_documented() -> None:
    content = _read_doc()

    _assert_contains_all(
        content,
        (
            "`GET /settings/usage-summary`",
            "`summarize_usage_logs()`",
            "`usage_logs.jsonl`",
            "BYOK",
            "`provider_cost_included=false`",
            "`quota_rejected`",
        ),
    )


def test_ui_ux_preservation_rules_are_documented() -> None:
    content = _read_doc()

    _assert_contains_all(
        content,
        (
            "preserve existing UI",
            "no redesign",
            "no CSS unless explicitly required",
            "reuse existing classes",
            "client page is not admin page",
        ),
    )
