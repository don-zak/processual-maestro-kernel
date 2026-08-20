from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def assigned_literal(path: str, name: str):
    tree = ast.parse(read(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"missing assignment {name} in {path}")


def test_admin_layout_uses_general_owned_surface_map():
    source = read("processual_api/static/js/admin_layout_cleanup.js")
    assert "OWNED_ADMIN_SURFACES" in source
    assert "containOwnedAdminSurfaces" in source
    assert "data-admin-owner-page" not in source  # dataset camelCase is used instead
    assert "surface.dataset.adminOwnerPage = ownerPageId" in source
    assert "'admin-integration-readiness-tracking-summary-host': 'page-admin-home'" in source
    assert "'admin-integration-readiness-case-management-host': 'page-admin-clients'" in source
    assert "'admin-integration-claim-keys-host': 'page-admin-clients'" in source
    assert "'admin-integration-readiness-operator-package-host': 'page-operator-pilot-handoff'" in source


def test_vq_validator_rejects_cross_page_owned_surfaces_and_settings_noise():
    source = read("qualification/vq1_browser_state_validator.py")
    assert "validate_admin_surface_ownership" in source
    assert "visible owned surface outside active admin page" in source
    assert "refresh_clean_settings_evidence" in source
    assert "Failed to load client settings" in source
    assert 'evidence_path("/console/", "settings", "default/loaded")' in source
    assert 'evidence_path("/console/", "settings", "localization/RTL")' in source


def test_vq_authority_metadata_contract_covers_all_forbidden_promotions():
    flags = assigned_literal(
        "qualification/vq1_ui_state_matrix_extended.py",
        "REQUIRED_FALSE_AUTHORITY_FLAGS",
    )
    assert flags == (
        "RepositoryReconciliationComplete",
        "GeneralPackagingComplete",
        "PrivateRuntimeAuthorityGranted",
        "runtime_connector_approved",
        "provider_sandbox_proven",
        "operator_network_qos_proven",
        "RealStagingQualified",
        "ProductionAuthorityGranted",
    )
    source = read("qualification/vq1_ui_state_matrix_extended.py")
    assert "enforce_authority_metadata(metadata)" in source
    assert "attempted to promote forbidden flags" in source


def test_marketplace_permission_denied_rejects_owned_surface_leakage():
    source = read("qualification/vq1_ui_state_matrix_extended.py")
    for surface_id in (
        "admin-integration-readiness-tracking-summary-host",
        "admin-integration-readiness-case-management-host",
        "admin-integration-claim-keys-host",
        "admin-integration-readiness-operator-package-host",
    ):
        assert surface_id in source
    assert "permission-denied evidence contains cross-page owned surfaces" in source
