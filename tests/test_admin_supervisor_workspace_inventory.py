from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "admin_supervisor_workspace_inventory.md"


def test_admin_supervisor_workspace_inventory_document_exists() -> None:
    assert DOC.exists()


def test_admin_supervisor_workspace_inventory_covers_current_surfaces() -> None:
    source = DOC.read_text(encoding="utf-8")

    required_sections = [
        "Admin Home",
        "Supervisor Session",
        "API Keys",
        "Supervisor Session Keys",
        "Client Requests",
        "Provider",
        "Adapters",
        "Audit",
        "Health",
        "Billing",
        "Recommended next tools",
    ]

    for section in required_sections:
        assert section in source


def test_admin_supervisor_workspace_inventory_names_operational_metrics() -> None:
    source = DOC.read_text(encoding="utf-8")

    required_metrics = [
        "requests by status",
        "pending",
        "reviewed",
        "approved",
        "rejected",
        "completed",
        "draft saved",
        "response sent",
        "supervisor audit summary",
        "API key lifecycle summary",
    ]

    for metric in required_metrics:
        assert metric in source


def test_admin_supervisor_workspace_inventory_preserves_security_boundary() -> None:
    source = DOC.read_text(encoding="utf-8")

    assert "Backend enforcement remains authoritative" in source
    assert "Do not display raw supervisor session keys" in source
    assert "Do not display key_hash" in source
    assert "No extra hardening phase is planned here" in source
