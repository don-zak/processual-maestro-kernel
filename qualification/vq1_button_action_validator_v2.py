from __future__ import annotations

import json
from dataclasses import asdict

import vq1_button_action_validator as base
from vq1_browser_harness import establish_qualification_session

SETTINGS_TAB_STORAGE_KEY = "maestro_settings_tab"
SETTINGS_DEFAULT_TAB = "operations"
BUTTON_RESOLUTION_TIMEOUT_MS = 5000


def _ensure_session(page) -> None:
    establish_qualification_session(page)


def _reset_console_section_state(page, section: str) -> None:
    if section != "settings":
        return
    page.evaluate(
        """
        ({ key, value }) => {
          try {
            localStorage.setItem(key, value);
          } catch (_) {}
          try {
            sessionStorage.setItem(key, value);
          } catch (_) {}
        }
        """,
        {"key": SETTINGS_TAB_STORAGE_KEY, "value": SETTINGS_DEFAULT_TAB},
    )


def navigate_console(page, section: str) -> str:
    _ensure_session(page)
    _reset_console_section_state(page, section)
    page.goto(f"{base.BASE_URL}/console/", wait_until="domcontentloaded")
    selector = f'.nav-btn[data-page="{section}"]'
    button = page.locator(selector)
    try:
        button.wait_for(state="visible", timeout=5000)
    except Exception as exc:
        raise RuntimeError(
            f"Console navigation button {section!r} did not become visible; "
            f"current_url={page.url} selector={selector}"
        ) from exc
    button.click(timeout=5000)
    target = page.locator(f"#page-{section}")
    try:
        target.wait_for(state="visible", timeout=5000)
    except Exception as exc:
        raise RuntimeError(
            f"Console section {section!r} did not become visible after click; "
            f"current_url={page.url}"
        ) from exc
    return f"#page-{section}:visible"


def navigate_admin(page, section: str) -> str:
    _ensure_session(page)
    page.goto(f"{base.BASE_URL}/admin", wait_until="domcontentloaded")
    selector = f'.nav-btn[data-admin-page="{section}"]'
    button = page.locator(selector)
    try:
        button.wait_for(state="visible", timeout=5000)
    except Exception as exc:
        raise RuntimeError(
            f"Admin navigation button {section!r} did not become visible; "
            f"current_url={page.url} selector={selector}"
        ) from exc
    button.click(timeout=5000)
    page.wait_for_timeout(250)
    return ".admin-page.active"


def _accessible_label(button) -> str:
    return (
        button.inner_text()
        or button.get_attribute("aria-label")
        or button.get_attribute("title")
        or ""
    ).strip()


def _resolve_button_after_reload(page, scope: str, item: dict[str, object]):
    index = int(item["index"])
    label = str(item.get("label") or "").strip()
    button_id = str(item.get("id") or "")

    if button_id:
        stable = page.locator(f"#{button_id}")
        try:
            stable.wait_for(state="visible", timeout=BUTTON_RESOLUTION_TIMEOUT_MS)
        except Exception:
            pass
        else:
            return stable, "stable-id"

    by_label = page.locator(scope).get_by_role("button", name=label, exact=True)
    try:
        by_label.first.wait_for(state="visible", timeout=BUTTON_RESOLUTION_TIMEOUT_MS)
    except Exception:
        pass
    else:
        for candidate_index in range(by_label.count()):
            candidate = by_label.nth(candidate_index)
            if candidate.is_visible():
                return candidate, "accessible-label"

    buttons = page.locator(f"{scope} button:visible")
    if buttons.count() > index:
        candidate = buttons.nth(index)
        if _accessible_label(candidate) == label:
            return candidate, "stable-index-and-label"

    return None, "not-found"


def exercise_section_buttons(
    page,
    *,
    surface: str,
    section: str,
    openapi_paths: dict[str, object],
):
    navigate = navigate_console if surface == "console" else navigate_admin
    scope = navigate(page, section)
    initial = base.button_inventory(page, scope)
    results = []

    for item in initial:
        index = int(item["index"])
        label = str(item.get("label") or "").strip()
        button_id = str(item.get("id") or "")
        disabled = bool(item.get("disabled"))
        if not label:
            results.append(
                base.ButtonResult(surface, section, index, label, button_id, disabled, "FAIL", [], [], "visible button has no accessible label")
            )
            continue
        if disabled:
            results.append(
                base.ButtonResult(surface, section, index, label, button_id, True, "CONDITIONAL", ["disabled-by-state"], [], "disabled control recorded; executable prerequisites are state-dependent")
            )
            continue

        scope = navigate(page, section)
        button, resolution = _resolve_button_after_reload(page, scope, item)
        if button is None:
            results.append(
                base.ButtonResult(
                    surface,
                    section,
                    index,
                    label,
                    button_id,
                    False,
                    "FAIL",
                    [],
                    [],
                    "button identity no longer visible after deterministic reload",
                )
            )
            continue

        events = []
        response_status = {}
        dialogs = []
        downloads = []

        def on_request(request) -> None:
            if base.same_origin(request.url):
                events.append({"method": request.method, "url": request.url, "path": base.request_path(request.url)})

        def on_response(response) -> None:
            request = response.request
            if base.same_origin(request.url):
                response_status[(request.method, request.url)] = response.status

        def on_dialog(dialog) -> None:
            dialogs.append(dialog.type)
            dialog.accept()

        def on_download(download) -> None:
            downloads.append(download.suggested_filename)

        page.on("request", on_request)
        page.on("response", on_response)
        page.on("dialog", on_dialog)
        page.on("download", on_download)

        before_url = page.url
        before_scope = base.scope_signature(page, scope)
        before_storage = base.storage_snapshot(page)
        before_probe = base.probe_snapshot(page)
        before_focus = page.evaluate("() => document.activeElement?.outerHTML || ''")
        before_disabled = button.is_disabled()
        before_text = (button.inner_text() or "").strip()
        before_expanded = button.get_attribute("aria-expanded")

        click_error = ""
        try:
            button.click(timeout=2500)
            page.wait_for_timeout(650)
        except Exception as exc:
            click_error = str(exc).splitlines()[0]

        after_url = page.url
        after_scope = base.scope_signature(page, scope) if page.locator(scope).count() else ""
        after_storage = base.storage_snapshot(page)
        after_probe = base.probe_snapshot(page)
        after_focus = page.evaluate("() => document.activeElement?.outerHTML || ''")
        after_disabled = button.is_disabled() if button.count() else before_disabled
        after_text = (button.inner_text() or "").strip() if button.count() else ""
        after_expanded = button.get_attribute("aria-expanded") if button.count() else None

        page.remove_listener("request", on_request)
        page.remove_listener("response", on_response)
        page.remove_listener("dialog", on_dialog)
        page.remove_listener("download", on_download)

        effects = []
        if events:
            effects.append("request")
        if before_url != after_url:
            effects.append("navigation")
        if before_scope != after_scope:
            effects.append("dom-state")
        if before_storage != after_storage:
            effects.append("storage")
        if before_probe != after_probe:
            effects.append("browser-api")
        if before_focus != after_focus:
            effects.append("focus-or-validation")
        if before_disabled != after_disabled or before_text != after_text:
            effects.append("button-state")
        if before_expanded != after_expanded:
            effects.append("expanded-state")
        if dialogs:
            effects.append("dialog")
        if downloads:
            effects.append("download")

        request_records = []
        route_failures = []
        for event in events:
            method = str(event["method"])
            url = str(event["url"])
            path = str(event["path"])
            status_code = response_status.get((method, url))
            request_records.append({"method": method, "path": path, "status": status_code})
            if base.is_api_candidate(path) and method in base.MUTATION_METHODS and not base.openapi_match(openapi_paths, method, path):
                route_failures.append(f"{method} {path} is not registered in OpenAPI")
            if status_code in {405}:
                route_failures.append(f"{method} {path} returned HTTP {status_code}")

        status = "PASS"
        notes = [f"resolved_by={resolution}"]
        if click_error:
            status = "FAIL"
            notes.append(f"click failed: {click_error}")
        if not effects:
            status = "FAIL"
            notes.append("click produced no observable execution effect")
        if route_failures:
            status = "FAIL"
            notes.extend(route_failures)

        results.append(
            base.ButtonResult(
                surface=surface,
                section=section,
                index=index,
                label=label,
                button_id=button_id,
                disabled=False,
                status=status,
                effects=effects,
                requests=request_records,
                notes="; ".join(notes),
            )
        )

    return results


def print_report() -> None:
    if not base.REPORT_PATH.exists():
        print(f"Button audit report was not created: {base.REPORT_PATH}")
        return
    payload = json.loads(base.REPORT_PATH.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    print("\n=== BUTTON ACTION AUDIT SUMMARY ===")
    print(f"ALL:         {totals.get('all', 0)}")
    print(f"PASS:        {totals.get('pass', 0)}")
    print(f"CONDITIONAL: {totals.get('conditional', 0)}")
    print(f"FAIL:        {totals.get('fail', 0)}")
    failures = [item for item in payload.get("results", []) if item.get("status") == "FAIL"]
    if failures:
        print("\nFailures:")
        for item in failures[:40]:
            print(
                f"- {item.get('surface')}/{item.get('section')} :: "
                f"{item.get('label') or '<unlabelled>'} :: {item.get('notes') or 'no detail'}"
            )
    print(f"\nReport: {base.REPORT_PATH}")


def write_fatal_report(exc: Exception) -> None:
    base.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": base.BASE_URL,
        "scope": "all delivered Console/Admin navigation plus all visible buttons in each active section",
        "totals": {"all": 0, "pass": 0, "conditional": 0, "fail": 1},
        "fatal_error": str(exc),
        "results": [
            asdict(
                base.ButtonResult(
                    surface="audit",
                    section="bootstrap-or-navigation",
                    index=-1,
                    label="Button action audit",
                    button_id="",
                    disabled=False,
                    status="FAIL",
                    effects=[],
                    requests=[],
                    notes=str(exc),
                )
            )
        ],
    }
    base.REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    base.navigate_console = navigate_console
    base.navigate_admin = navigate_admin
    base.exercise_section_buttons = exercise_section_buttons
    try:
        base.main()
    except Exception as exc:
        if not base.REPORT_PATH.exists():
            write_fatal_report(exc)
        print_report()
        raise
    else:
        print_report()


if __name__ == "__main__":
    main()
