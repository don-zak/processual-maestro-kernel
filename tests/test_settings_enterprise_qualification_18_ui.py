from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "processual_api" / "static" / "js" / "settings_enterprise_console_18.js"
SCRIPT = ROOT / "processual_api" / "static" / "js" / "settings_enterprise_qualification_18.js"
STYLE = ROOT / "processual_api" / "static" / "css" / "settings_enterprise_qualification_18.css"


def test_qualification_extension_is_bootstrapped_by_enterprise_console() -> None:
    source = CONSOLE.read_text(encoding="utf-8")

    assert "ensureQualificationExtension" in source
    assert "settings_enterprise_qualification_18.css" in source
    assert "settings_enterprise_qualification_18.js" in source
    assert "PMK_SETTINGS_ENTERPRISE_QUALIFICATION_18?.init?.()" in source


def test_qualification_workspace_uses_server_catalog_and_server_evaluation() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "payload?.qualification_catalog" in source
    assert "catalog.profiles" in source
    assert "catalog.scopes" in source
    assert "profile?.allowed_scope_ids" in source
    assert ".filter((scope) => allowed.has(scope.scope_id))" in source
    assert "CLIENT.post(QUALIFY_ENDPOINT" in source
    assert "credential_profile_id" in source
    assert "requested_scope_ids" in source
    assert "provided_input_ids" in source
    assert "Evaluation is not persisted" in source
    assert "Runtime connector approval cannot be granted" in source


def test_qualification_workspace_has_no_secret_value_fields_or_approval_controls() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "input.type = 'checkbox'" in source
    assert "document.createElement('select')" in source
    assert "input.type = 'text'" not in source
    assert "input.type = 'password'" not in source
    post_body = source.split("CLIENT.post(QUALIFY_ENDPOINT", 1)[1].split("});", 1)[0]
    assert "security_controls_approved" not in post_body
    assert "required_security_control_ids" not in post_body
    assert "Do not enter API keys, passwords, tokens" in source
    assert "never paste the underlying value" in source
    assert ".innerHTML =" not in source


def test_qualification_workspace_is_accessible_responsive_and_fail_closed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    style = STYLE.read_text(encoding="utf-8")

    assert "aria-labelledby" in source
    assert "aria-live', 'polite'" in source
    assert "aria-busy" in source
    assert "No approval was inferred" in source
    assert "Production remains blocked" in source
    assert "@media (max-width: 760px)" in style
    assert "@media (prefers-reduced-motion: reduce)" in style
    assert "border-inline-start" in style
    assert "overflow-wrap: anywhere" in style
    assert ":focus-visible" in style
