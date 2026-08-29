from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "showcase"


RUNTIME_FORBIDDEN = (
    "http://localhost",
    "https://localhost",
    "fetch(",
    "XMLHttpRequest",
    "MAESTRO_ADMIN_PASSWORD",
    "API_KEYS",
)


def test_showcase_files_exist() -> None:
    required = {
        "MAESTRO_SHOWCASE.html",
        "MAESTRO_DEMO.html",
        "TASK-LAB.html",
        "START-SHOWCASE.ps1",
        "README.md",
    }
    assert required <= {path.name for path in SHOWCASE.iterdir()}


def test_all_browser_showcase_pages_are_runtime_independent() -> None:
    for name in ("MAESTRO_SHOWCASE.html", "MAESTRO_DEMO.html", "TASK-LAB.html"):
        html = (SHOWCASE / name).read_text(encoding="utf-8")
        for value in RUNTIME_FORBIDDEN:
            assert value not in html, f"{name} contains forbidden runtime dependency: {value}"


def test_showcase_marks_mock_and_recorded_boundaries() -> None:
    html = (SHOWCASE / "MAESTRO_SHOWCASE.html").read_text(encoding="utf-8")
    assert "DEMO / MOCK UI" in html
    assert "RECORDED EVIDENCE" in html
    assert "not a live provider call" in html
    assert "Production authority" in html
    assert "NOT GRANTED" in html


def test_showcase_contains_required_review_surfaces() -> None:
    html = (SHOWCASE / "MAESTRO_SHOWCASE.html").read_text(encoding="utf-8")
    for label in (
        "Operations Console",
        "Governance / CGT",
        "Admin Workspace",
        "Qualification Evidence",
        "Identity",
        "Authority",
        "Entitlement",
        "Quota",
        "Runtime Capacity",
        "Audit / Evidence",
    ):
        assert label in html


def test_task_lab_contains_multiple_governance_scenarios() -> None:
    html = (SHOWCASE / "TASK-LAB.html").read_text(encoding="utf-8")
    for label in (
        "SLA Incident Governance",
        "Privileged API Key Rotation",
        "Quota Pressure / Burst Workload",
        "Provider Degradation Recovery",
        "Sensitive Configuration Change",
        "External Evaluation Access",
        "Audit Evidence Review",
        "CONTROL",
        "CLARIFY",
        "REPAIR",
        "STOP",
        "CONTINUE",
        "Auto-run",
        "Next checkpoint",
    ):
        assert label in html


def test_unified_demo_embeds_task_library_and_review_surfaces() -> None:
    html = (SHOWCASE / "MAESTRO_DEMO.html").read_text(encoding="utf-8")
    assert 'src="TASK-LAB.html"' in html
    assert "Operations / Task Library" in html
    assert "Governance / CGT" in html
    assert "Admin Workspace" in html
    assert "Qualification" in html
    assert "DEMO / MOCK UI" in html
    assert "Production authority" in html


def test_launcher_has_no_runtime_or_secret_dependency() -> None:
    launcher = (SHOWCASE / "START-SHOWCASE.ps1").read_text(encoding="utf-8")
    assert "Start-Process" in launcher
    assert "docker" not in launcher.lower()
    assert "password" in launcher.lower()
    assert "api key" in launcher.lower()
    assert "No Docker, login, password, API key or runtime is required." in launcher
