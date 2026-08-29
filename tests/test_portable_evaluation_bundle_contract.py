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
        "SHOW-EVALUATION-ACCESS.ps1",
        "EVALUATION_HOME.html",
        "GUIDED-DEMO.md",
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


def test_windows_launcher_opens_reviewer_home_instead_of_api_docs() -> None:
    powershell = (EVAL / "START-MAESTRO.ps1").read_text(encoding="utf-8")
    assert "EVALUATION_HOME.html" in powershell
    assert "SHOW-EVALUATION-ACCESS.ps1" in powershell
    assert "Start-Process 'http://localhost:8000/docs'" not in powershell


def test_evaluation_access_helper_hides_secrets_by_default() -> None:
    helper = (EVAL / "SHOW-EVALUATION-ACCESS.ps1").read_text(encoding="utf-8")
    assert "[switch]$ShowSecrets" in helper
    assert "Secrets are hidden by default" in helper
    assert "MAESTRO_ADMIN_PASSWORD" in helper
    assert "API_KEYS" in helper


def test_reviewer_home_is_self_contained_and_points_to_local_runtime() -> None:
    home = (EVAL / "EVALUATION_HOME.html").read_text(encoding="utf-8")
    assert "http://localhost:8000/console" in home
    assert "http://localhost:8000/admin" in home
    assert "http://localhost:8000/docs" in home
    assert "Startup Tunisia Evaluation Edition" in home
    assert "fonts.googleapis.com" not in home
    assert "cdn.jsdelivr.net" not in home


def test_guided_demo_uses_synthetic_data_and_preserves_evidence_boundary() -> None:
    guide = (EVAL / "GUIDED-DEMO.md").read_text(encoding="utf-8")
    assert "Enterprise Incident / Ticket Governance" in guide
    assert "Use synthetic data only" in guide
    assert "Do not describe Mock/Sandbox evidence as Production" in guide
    assert "private CGT" in guide
