from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"


def test_portable_evaluation_files_exist() -> None:
    required = {
        "docker-compose.evaluation.yml",
        ".env.evaluation.example",
        "START-MAESTRO.ps1",
        "STOP-MAESTRO.ps1",
        "CHECK-STATUS.ps1",
        "RESET-DEMO.ps1",
        "LOAD-OFFLINE-IMAGES.ps1",
        "start-maestro.sh",
        "README_START_HERE.md",
    }
    assert required <= {path.name for path in EVAL.iterdir()}


def test_evaluation_compose_uses_public_prebuilt_image_and_local_dependencies() -> None:
    compose = (EVAL / "docker-compose.evaluation.yml").read_text(encoding="utf-8")
    assert "processual-maestro-evaluation:${MAESTRO_EVAL_IMAGE_TAG:-v1}" in compose
    assert "postgres:17-alpine" in compose
    assert "redis:7-alpine" in compose
    assert "cgtlib/private" not in compose


def test_evaluation_template_is_fail_closed_for_money_and_external_llm() -> None:
    env = (EVAL / ".env.evaluation.example").read_text(encoding="utf-8")
    assert "MAESTRO_TOP_UP_PURCHASE_ENABLED=false" in env
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ENABLED=false" in env
    assert "MAESTRO_LOCAL_TUNISIA_TOP_UP_ADMIN_ENABLED=false" in env
    assert "LEMONSQUEEZY_API_KEY=\n" in env
    assert "OPENCODE_API_URL=http://127.0.0.1:9/v1" in env
    assert "OPENCODE_API_KEY=evaluation-disabled" in env


def test_launchers_generate_secrets_instead_of_shipping_runtime_values() -> None:
    powershell = (EVAL / "START-MAESTRO.ps1").read_text(encoding="utf-8")
    posix = (EVAL / "start-maestro.sh").read_text(encoding="utf-8")
    assert "RandomNumberGenerator" in powershell
    assert ".env.evaluation" in powershell
    assert "/dev/urandom" in posix
    assert ".env.evaluation" in posix
