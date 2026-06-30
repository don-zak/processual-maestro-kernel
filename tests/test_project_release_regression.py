from pathlib import Path
import importlib

ROOT = Path(__file__).resolve().parents[1]


def test_release_report_documents_current_regression_coverage():
    report = ROOT / "docs" / "reports" / "API_KEYS_ADAPTERS_REGRESSION_REPORT.md"

    assert report.is_file(), "Missing API keys/adapters regression report"

    text = report.read_text(encoding="utf-8")
    required_markers = [
        "TEST-05A",
        "TEST-06A",
        "TEST-06B",
        "TEST-07A",
        "TEST-07B",
        "TEST-08A",
        "TEST-09A",
        "TEST-10A",
        "TEST-11A",
        "TEST-12A",
        "85 passed",
        "6 warnings",
    ]

    missing = [marker for marker in required_markers if marker not in text]
    assert not missing, f"Missing release regression markers: {missing}"


def test_release_critical_project_paths_exist():
    required_paths = [
        ROOT / "processual_api" / "main.py",
        ROOT / "processual_api" / "routers",
        ROOT / "processual_api" / "services",
        ROOT / "processual_api" / "adapters",
        ROOT / "processual_api" / "auth",
        ROOT / "processual_api" / "middleware",
        ROOT / "processual_kernel",
        ROOT / "cgtlib",
        ROOT / "tests",
        ROOT / "docs",
        ROOT / "docs" / "reports",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    assert not missing, f"Missing critical release paths: {missing}"


def test_release_has_readme_and_python_dependency_manifest():
    readmes = list(ROOT.glob("README*"))
    assert readmes, "Missing README file"

    manifests = [
        ROOT / "pyproject.toml",
        ROOT / "requirements.txt",
        ROOT / "requirements-dev.txt",
    ]
    assert any(path.is_file() for path in manifests), "Missing Python dependency manifest"


def test_release_core_modules_are_importable():
    modules = [
        "processual_api.main",
        "processual_kernel",
        "cgtlib",
    ]

    for module_name in modules:
        importlib.import_module(module_name)


def test_release_static_console_directories_exist():
    static_root = ROOT / "processual_api" / "static"
    required_static_paths = [
        static_root,
        static_root / "css",
        static_root / "js",
        static_root / "js" / "adapters",
        static_root / "js" / "pages",
    ]

    missing = [str(path.relative_to(ROOT)) for path in required_static_paths if not path.exists()]
    assert not missing, f"Missing static console paths: {missing}"