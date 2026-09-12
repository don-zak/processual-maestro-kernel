from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/evaluation-owned-sandbox-cloudflare.yml")


def _source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_cloudflare_worker_deploy_is_manual_only() -> None:
    source = _source()

    assert "workflow_dispatch:" in source
    assert "push:" not in source
    assert "pull_request:" not in source
    assert "environment: external-evaluation-sandbox" in source
    assert "runs-on: ubuntu-latest" in source


def test_cloudflare_deploy_is_pinned_to_requested_exact_ref() -> None:
    source = _source()

    assert "expected_ref:" in source
    assert "ref: ${{ inputs.expected_ref }}" in source
    assert 'actual="$(git rev-parse HEAD)"' in source
    assert 'test "$actual" = "${{ inputs.expected_ref }}"' in source
    assert "persist-credentials: false" in source


def test_cloudflare_deploy_runs_owned_scenario_contract_tests_first() -> None:
    source = _source()

    assert "tests/test_external_evaluation_owned_crm_scenarios.py" in source
    assert "tests/test_external_evaluation_owned_integration_scenarios.py" in source
    assert "tests/test_evaluation_owned_sandbox_contract.py" in source
    assert source.index("Verify owned Evaluation scenario contracts") < source.index(
        "Deploy project-owned Evaluation sandbox with pinned Wrangler"
    )


def test_cloudflare_deploy_uses_secret_references_without_secret_values() -> None:
    source = _source()

    assert "${{ secrets.CLOUDFLARE_API_TOKEN }}" in source
    assert "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}" in source
    assert "CLOUDFLARE_API_TOKEN is not configured" in source
    assert "CLOUDFLARE_ACCOUNT_ID is not configured" in source
    assert "CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}" in source
    assert "CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}" in source
    assert "token_value" not in source.lower()
    assert "account_value" not in source.lower()


def test_cloudflare_deploy_uses_exact_pinned_wrangler_without_package_lock_dependency() -> None:
    source = _source()

    assert "npx --yes wrangler@4.131.1 deploy" in source
    assert "npm ci" not in source
    assert "package-lock.json" not in source
    assert 'cache: "npm"' not in source
