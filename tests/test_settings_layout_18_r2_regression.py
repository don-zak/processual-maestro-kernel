from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LAYOUT_JS = (
    ROOT
    / "processual_api"
    / "static"
    / "js"
    / "settings_layout_18.js"
)

LAYOUT_CSS = (
    ROOT
    / "processual_api"
    / "static"
    / "css"
    / "settings_layout_18.css"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_settings_r2_defines_five_independent_tabs() -> None:
    source = _read(LAYOUT_JS)

    expected = (
        "{ key: 'operations', label: 'Operations' }",
        "{ key: 'account', label: 'Account' }",
        "{ key: 'usage', label: 'Plan & usage' }",
        "{ key: 'integration', label: 'Integration' }",
        "{ key: 'support', label: 'Escalations' }",
    )

    for marker in expected:
        assert marker in source

    assert "role=\"tab\"" in source
    assert "role', 'tabpanel'" in source
    assert "aria-selected" in source
    assert "panel.hidden = !active" in source


def test_settings_r2_reconciles_late_rendered_cards() -> None:
    source = _read(LAYOUT_JS)

    assert "function reconcile()" in source
    assert "function scheduleReconcile()" in source
    assert "new MutationObserver" in source
    assert "observer.observe(page" in source
    assert "childList: true" in source
    assert "subtree: true" in source

    assert "window.setTimeout(reconcile, 100)" in source
    assert "window.setTimeout(reconcile, 500)" in source
    assert "window.setTimeout(reconcile, 1500)" in source


def test_settings_r2_keeps_only_selected_panel_visible() -> None:
    source = _read(LAYOUT_JS)
    css = _read(LAYOUT_CSS)

    assert "panel.classList.toggle('active', active)" in source
    assert "panel.hidden = !active" in source

    assert ".sl18-panel {" in css
    assert "display: none;" in css
    assert ".sl18-panel[hidden]" in css
    assert ".sl18-panel.active" in css
    assert "display: flex;" in css


def test_settings_r2_merges_escalation_surfaces_without_removing_controls() -> None:
    source = _read(LAYOUT_JS)

    assert "function mergeEscalationCards()" in source
    assert "'Escalations & support'" in source
    assert "'Direct supervisor message'" in source
    assert "requests.appendChild(support)" in source

    assert (
        "Billing, plan, security, or approval exceptions only"
        in source
    )

    assert (
        "Use only when direct operations cannot resolve the issue"
        in source
    )

    assert "'set-client-requests-card'" in source
    assert "'set-client-support-card'" in source


def test_settings_r2_preserves_default_deny_and_safe_layout_contracts() -> None:
    source = _read(LAYOUT_JS)
    css = _read(LAYOUT_CSS)

    assert "'sl18-provider-direct'" in source
    assert "'sl18-hidden'" in source
    assert "'set-provider-setup-request-prepare'" in source

    assert ".sl18-hidden" in css
    assert "display: none !important;" in css
    assert ".sl18-escalation-subsection" in css
    assert ".sl18-escalation-card" in css


def test_settings_r2_responsive_tabs_do_not_force_page_width() -> None:
    css = _read(LAYOUT_CSS)

    assert "@media (max-width: 900px)" in css
    assert "overflow-x: auto;" in css
    assert "flex: 0 0 auto;" in css
    assert "grid-template-columns: 1fr;" in css
