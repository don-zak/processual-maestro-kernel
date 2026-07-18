from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "processual_api" / "static"


def read_static(name: str) -> str:
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def test_admin_home_has_meaningful_operations_overview():
    html = read_static("admin.html")

    required = [
        "ADMIN OPERATIONS OVERVIEW",
        "Supervisor workspace for clients, usage, providers, API keys, and system readiness",
        "monitor customers and pilots",
        "track Maestro usage",
        "review provider readiness",
        "follow deployment progress",
    ]

    for token in required:
        assert token in html


def test_admin_area_includes_supervisor_productization_sections():
    html = read_static("admin.html")

    required = [
        "Clients",
        "Usage Monitor",
        "Program Progress",
        "System Health",
        "Bridge to Client Console",
        "evaluations used",
        "provider connection status",
        "Cloud Run readiness",
    ]

    for token in required:
        assert token in html
