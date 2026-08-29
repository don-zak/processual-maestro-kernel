from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "showcase"


def test_showcase_files_exist() -> None:
    required = {"MAESTRO_SHOWCASE.html", "START-SHOWCASE.ps1", "README.md"}
    assert required <= {path.name for path in SHOWCASE.iterdir()}


def test_showcase_is_runtime_independent() -> None:
    html = (SHOWCASE / "MAESTRO_SHOWCASE.html").read_text(encoding="utf-8")
    forbidden = (
        "http://localhost",
        "https://localhost",
        "fetch(",
        "XMLHttpRequest",
        "MAESTRO_ADMIN_PASSWORD",
        "API_KEYS",
    )
    for value in forbidden:
        assert value not in html


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


def test_launcher_has_no_runtime_or_secret_dependency() -> None:
    launcher = (SHOWCASE / "START-SHOWCASE.ps1").read_text(encoding="utf-8")
    assert "Start-Process" in launcher
    assert "docker" not in launcher.lower()
    assert "password" in launcher.lower()
    assert "api key" in launcher.lower()
    assert "No Docker, login, password, API key or runtime is required." in launcher
