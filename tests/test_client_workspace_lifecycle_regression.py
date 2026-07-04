from pathlib import Path

SETTINGS_JS = Path("processual_api/static/js/pages/settings.js")


def _function_body(js: str, name: str) -> str:
    start = js.index(f"  function {name}(")
    next_start = js.find("\n  function ", start + 1)
    if next_start == -1:
        return js[start:]
    return js[start:next_start]


def test_client_workspace_launch_actions_use_idempotent_binding() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    body = _function_body(js, "initClientLaunchActions")

    expected = (
        (
            'bindClientWorkspaceActionButton("set-launch-primary-action", '
            "handleClientLaunchPrimaryAction);"
        ),
        (
            'bindClientWorkspaceActionButton("set-launch-secondary-action", '
            "openClientLaunchRequests);"
        ),
    )
    for marker in expected:
        assert marker in body

    forbidden_direct_handlers = (
        'document.getElementById("set-launch-primary-action")?.addEventListener',
        'document.getElementById("set-launch-secondary-action")?.addEventListener',
    )
    for marker in forbidden_direct_handlers:
        assert marker not in body

    assert "function openClientLaunchRequests" in js


def test_client_workspace_action_center_actions_remain_idempotent() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    body = _function_body(js, "initClientLaunchActions")

    expected = (
        (
            'bindClientWorkspaceActionButton("set-action-center-provider-action", '
            "prepareActionCenterProviderSetup);"
        ),
        (
            'bindClientWorkspaceActionButton("set-action-center-usage-action", '
            "prepareActionCenterUsageReview);"
        ),
        (
            'bindClientWorkspaceActionButton("set-action-center-integration-action", '
            "prepareActionCenterIntegrationKey);"
        ),
        (
            'bindClientWorkspaceActionButton("set-action-center-requests-action", '
            "openActionCenterRequests);"
        ),
    )
    for marker in expected:
        assert marker in body


def test_client_workspace_binding_guard_prevents_repeated_navigation_handlers() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    guard = _function_body(js, "bindClientWorkspaceActionButton")

    assert 'button.dataset.workspaceActionBound === "1"' in guard
    assert 'button.dataset.workspaceActionBound = "1";' in guard
    assert 'button.addEventListener("click", handler);' in guard
    assert "if (settingsInitDone)" in js
    assert js.count("initClientLaunchActions();") == 2


def test_client_workspace_lifecycle_patch_stays_client_safe() -> None:
    js = SETTINGS_JS.read_text(encoding="utf-8")
    body = _function_body(js, "initClientLaunchActions")

    forbidden = (
        "/settings/api-keys",
        "/settings/llm-provider",
        "/admin",
        "encrypted_key",
        "api_key",
    )
    for marker in forbidden:
        assert marker not in body
