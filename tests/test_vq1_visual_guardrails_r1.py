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
    assert "data-admin-owner-page" not in source
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


def test_live_admin_home_uses_one_canonical_surface_and_document_flow():
    source = read("processual_api/static/js/admin_home_layout.js")
    assert "CANONICAL_CARD_IDS" in source
    for card_id in (
        "admin-program-supervision-readiness",
        "admin-supervisor-overview-counters",
        "admin-integration-readiness-tracking-summary-host",
        "admin-runtime-home-summary",
        "admin-runtime-auth-state",
    ):
        assert card_id in source
    assert "admin-home-canonical-surface" in source
    assert "canonicalizeHomeCards" in source
    assert "surface.appendChild(node)" in source
    assert "contain:layout paint" in source
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in source
    assert "#admin-program-supervision-readiness,#admin-supervisor-overview-counters,#admin-integration-readiness-tracking-summary-host{grid-column:1/-1!important}" in source
    assert "overflow-x:hidden!important" in source
    assert "MutationObserver" in source


def test_admin_narrow_sidebar_hides_long_brand_text():
    source = read("processual_api/static/js/admin_home_layout.js")
    assert "@media (max-width:600px)" in source
    assert "#brand>div:last-child{display:none!important}" in source
    assert "#brand-mark{margin:0 auto!important}" in source


def test_admin_market_navigation_stays_visible_but_authority_remains_backend_controlled():
    layout = read("processual_api/static/js/admin_home_layout.js")
    marketplace = read("processual_api/static/js/admin_marketplace.js")
    assert "ensureMarketplaceNavigationVisible" in layout
    assert "visible-fail-closed" in layout
    assert "backend platform-administrator authority is required" in layout
    assert "response.status === 403 || response.status === 401" in marketplace
    assert "Platform authority required" in marketplace
    assert "Sign-in required" in marketplace


def test_login_restores_accessible_password_visibility_control():
    source = read("processual_api/static/js/login_token_capture.js")
    assert "installPasswordVisibilityControl" in source
    assert "login-password-visibility" in source
    assert "aria-pressed" in source
    assert "Show password" in source
    assert "Hide password" in source
    assert "password.type = visible ? 'password' : 'text'" in source


def test_console_badge_reports_qualification_readiness_without_production_authority():
    i18n = read("processual_api/static/js/i18n.js")
    app = read("processual_api/static/js/app.js")
    assert "Qualification Ready" in i18n
    assert "جاهز للتأهيل" in i18n
    assert "syncQualificationBadge" in app
    assert "controlled-review-ready" in app
    assert "no production authority is granted" in app


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
