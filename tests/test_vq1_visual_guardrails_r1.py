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


def test_admin_layout_normalizes_to_single_navigation_authority():
    source = read("processual_api/static/js/admin_layout_cleanup.js")
    assert "document.body?.dataset?.adminActivePage" in source
    assert "navApi?.pageIds" in source
    assert "page.classList.toggle('active', isActive)" in source
    assert "page.style.display = isActive ? 'block' : 'none'" in source
    assert "normalizeActivePage" in source


def test_long_card_enhancer_treats_readiness_host_as_structural():
    source = read("processual_api/static/js/long_card_collapse.js")
    assert "STRUCTURAL_HOST_IDS" in source
    assert "admin-integration-readiness-tracking-summary-host" in source
    assert "STRUCTURAL_HOST_IDS.has(card.id)" in source
    assert "isStructuralHostPanel(card)" in source
    assert "!isSemanticCard(card) || isStructuralHostPanel(card)" in source
    assert "admin-integration-readiness-tracking-summary-card" in source


def test_vq_validator_rejects_cross_page_owned_surfaces_and_settings_noise():
    source = read("qualification/vq1_browser_state_validator.py")
    assert "validate_admin_surface_ownership" in source
    assert "visible owned surface outside active admin page" in source
    assert "refresh_clean_settings_evidence" in source
    assert "Failed to load client settings" in source
    assert 'evidence_path("/console/", "settings", "default/loaded")' in source
    assert 'evidence_path("/console/", "settings", "localization/RTL")' in source


def test_settings_default_evidence_refresh_covers_every_recorded_viewport_before_upload():
    refresher = read("qualification/vq1_settings_default_evidence_refresh.py")
    workflow = read(".github/workflows/vq1-browser-qualification.yml")
    assert "def default_rows()" in refresher
    assert 'row["state"] == "default/loaded"' in refresher
    assert 'for row in rows:' in refresher
    assert 'width = int(row["viewport_width"])' in refresher
    assert 'height = int(row["viewport_height"])' in refresher
    assert 'page.screenshot(path=str(shot), full_page=True)' in refresher
    assert "Failed to load client settings" in refresher
    assert "BILLING_STATEMENTS_PAYLOAD" in refresher
    assert '"**/billing/statements"' in refresher
    assert "API_KEY_INTEGRATION_PAYLOAD" in refresher
    assert '"**/settings/api-key-integration"' in refresher
    assert '"enabled": False' in refresher
    assert '"runtime_connector_approved": False' in refresher
    assert "Subscription access is temporarily unavailable" in refresher
    assert "Choose Tour Language" in refresher
    assert "tour_completed" in refresher
    assert "tour_lang" in refresher
    refresh_step = "python qualification/vq1_settings_default_evidence_refresh.py"
    upload_step = "uses: actions/upload-artifact@v4"
    assert refresh_step in workflow
    assert workflow.index(refresh_step) < workflow.index(upload_step)


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
