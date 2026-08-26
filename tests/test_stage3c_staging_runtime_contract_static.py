import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance" / "staging_runtime_contract.json"
VALIDATOR = ROOT / "scripts" / "Test-PMKStagingRuntimeContract.ps1"
DOC = ROOT / "docs" / "STAGE_3C_STAGING_RUNTIME_READINESS.md"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_stage3c_contract_contains_policy_only_and_preserves_authority_boundary() -> None:
    contract = _contract()

    assert contract["repository_secret_values_allowed"] is False
    assert contract["real_staging_qualified"] is False
    assert contract["environment_contract"]["ENVIRONMENT"] == "production"
    assert contract["environment_contract"]["API_DEBUG"] == "false"
    assert contract["environment_contract"]["RATE_LIMIT_ENABLED"] == "true"
    assert contract["environment_contract"]["AUDIT_ENABLED"] == "true"
    assert "JWT_SECRET" in contract["required_secret_env"]
    assert "DATABASE_URL" in contract["required_secret_env"]
    assert "REDIS_URL" in contract["required_secret_env"]
    assert "AUTH_TOKEN_PEPPER" in contract["required_secret_env"]
    assert "CORS_ORIGINS" in contract["required_non_secret_env"]
    assert "*" in contract["forbidden_cors_origins"]


def test_stage3c_validator_never_records_secret_values() -> None:
    text = VALIDATOR.read_text(encoding="utf-8")

    assert "checked_variable_names" in text
    assert "secret_values_recorded = $false" in text
    assert "real_staging_qualified = $false" in text
    assert "production_authority_granted = $false" in text
    assert "MISSING_SECRET:$name" in text
    assert "WEAK_SECRET:$name" in text
    assert "CONFIG_MISMATCH:$name" in text
    assert "FORBIDDEN_CORS:$forbiddenOrigin" in text
    assert "ConvertTo-Json" in text
    assert "value =" not in text.split("$evidence =", 1)[1]


def test_stage3c_runtime_artifacts_are_excluded_from_git_and_docker_context() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".pmk-validation/" in gitignore
    assert ".pmk-validation" in dockerignore or ".pmk-validation/" in dockerignore
    assert ".env.*" in dockerignore


def test_stage3c_documentation_keeps_real_staging_false() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "prepares the repository and runtime contract for real staging" in text
    assert "must never contain credentials" in text
    assert "does not serialize secret values" in text
    assert "RealStagingQualified = false" in text
    assert "ProductionAuthorityGranted = false" in text
    assert "Commercial Launch = NO-GO" in text
