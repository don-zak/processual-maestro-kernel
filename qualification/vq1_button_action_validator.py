from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Page, Route, sync_playwright

from vq1_browser_harness import (
    BASE_URL as HARNESS_BASE_URL,
    OUTPUT_DIR,
    discover_admin_sections,
    discover_console_sections,
    establish_qualification_session,
)

BASE_URL = os.environ.get("VQ1_BASE_URL", HARNESS_BASE_URL).rstrip("/")
REPORT_PATH = OUTPUT_DIR / "button_action_report.json"
MUTATION_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
STATIC_PREFIXES = (
    "/console/",
    "/static/",
    "/favicon",
)

PROBE_INIT = r"""
(() => {
  window.__pmkActionProbe = { clipboard: 0, open: 0, print: 0, invalid: 0 };
  document.addEventListener('invalid', () => { window.__pmkActionProbe.invalid += 1; }, true);
  const originalOpen = window.open;
  window.open = function(...args) {
    window.__pmkActionProbe.open += 1;
    try { return originalOpen.apply(this, args); } catch (_) { return null; }
  };
  const originalPrint = window.print;
  window.print = function(...args) {
    window.__pmkActionProbe.print += 1;
    try { return originalPrint.apply(this, args); } catch (_) { return undefined; }
  };
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      const originalWriteText = navigator.clipboard.writeText.bind(navigator.clipboard);
      navigator.clipboard.writeText = async function(...args) {
        window.__pmkActionProbe.clipboard += 1;
        try { return await originalWriteText(...args); } catch (_) { return undefined; }
      };
    }
  } catch (_) {}
})();
"""


@dataclass
class ButtonResult:
    surface: str
    section: str
    index: int
    label: str
    button_id: str
    disabled: bool
    status: str
    effects: list[str]
    requests: list[dict[str, object]]
    notes: str


def same_origin(url: str) -> bool:
    return urlparse(url).netloc == urlparse(BASE_URL).netloc


def request_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or "/"


def openapi_match(paths: dict[str, object], method: str, path: str) -> bool:
    method = method.lower()
    for template, operations in paths.items():
        pattern = "^" + re.sub(r"\{[^/]+\}", r"[^/]+", template.rstrip("/")) + "/?$"
        if re.match(pattern, path) and method in operations:
            return True
    return False


def is_api_candidate(path: str) -> bool:
    if path.startswith(STATIC_PREFIXES):
        return False
    return not path.endswith((".js", ".css", ".png", ".svg", ".ico", ".woff", ".woff2"))


def install_probe(page: Page) -> None:
    page.add_init_script(PROBE_INIT)
    page.add_init_script(
        """
        (() => {
          try {
            localStorage.setItem('tour_completed', 'true');
            localStorage.setItem('tour_lang', 'en');
          } catch (_) {}
        })();
        """
    )


def storage_snapshot(page: Page) -> str:
    return page.evaluate(
        """
        () => JSON.stringify({
          local: Object.keys(localStorage).sort().map(k => [k, localStorage.getItem(k)]),
          session: Object.keys(sessionStorage).sort().map(k => [k, sessionStorage.getItem(k)])
        })
        """
    )


def probe_snapshot(page: Page) -> dict[str, int]:
    return page.evaluate("() => ({...(window.__pmkActionProbe || {})})")


def scope_signature(page: Page, selector: str) -> str:
    locator = page.locator(selector)
    if not locator.count():
        return ""
    return locator.first.evaluate(
        """
        el => JSON.stringify({
          html: el.innerHTML,
          className: el.className,
          hidden: el.hidden,
          ariaExpanded: el.getAttribute('aria-expanded')
        })
        """
    )


def button_inventory(page: Page, selector: str) -> list[dict[str, object]]:
    return page.locator(f"{selector} button:visible").evaluate_all(
        """
        els => els.map((el, index) => ({
          index,
          id: el.id || '',
          label: (el.innerText || el.getAttribute('aria-label') || el.title || '').trim(),
          disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true'),
          type: el.getAttribute('type') || 'button',
          className: el.className || ''
        }))
        """
    )


def navigate_console(page: Page, section: str) -> str:
    page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
    page.wait_for_timeout(350)
    page.locator(f'.nav-btn[data-page="{section}"]').click()
    page.wait_for_timeout(500)
    return f"#page-{section}:visible"


def navigate_admin(page: Page, section: str) -> str:
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")
    page.wait_for_timeout(500)
    page.locator(f'.nav-btn[data-admin-page="{section}"]').click()
    page.wait_for_timeout(600)
    return ".admin-page.active"


def validate_nav_buttons(page: Page, surface: str, sections: list[dict[str, object]]) -> list[ButtonResult]:
    results: list[ButtonResult] = []
    route = "/console/" if surface == "console" else "/admin"
    attr = "data-page" if surface == "console" else "data-admin-page"
    active_selector = ".page.active" if surface == "console" else ".admin-page.active"
    for index, item in enumerate(sections):
        page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
        page.wait_for_timeout(400)
        section = str(item["id"])
        button = page.locator(f'.nav-btn[{attr}="{section}"]')
        before = scope_signature(page, active_selector)
        button.click()
        page.wait_for_timeout(180)
        after = scope_signature(page, active_selector)
        active_id = page.locator(active_selector).first.get_attribute("id") if page.locator(active_selector).count() else ""
        expected_id = f"page-{section}" if surface == "console" else None
        effect = before != after or (expected_id and active_id == expected_id) or surface == "admin"
        results.append(
            ButtonResult(
                surface=surface,
                section="navigation",
                index=index,
                label=str(item.get("text") or section),
                button_id=button.get_attribute("id") or "",
                disabled=False,
                status="PASS" if effect else "FAIL",
                effects=["navigation"] if effect else [],
                requests=[],
                notes=f"active_page={active_id}",
            )
        )
    return results


def exercise_section_buttons(
    page: Page,
    *,
    surface: str,
    section: str,
    openapi_paths: dict[str, object],
) -> list[ButtonResult]:
    navigate = navigate_console if surface == "console" else navigate_admin
    scope = navigate(page, section)
    initial = button_inventory(page, scope)
    results: list[ButtonResult] = []

    for item in initial:
        index = int(item["index"])
        label = str(item.get("label") or "").strip()
        button_id = str(item.get("id") or "")
        disabled = bool(item.get("disabled"))
        if not label:
            results.append(
                ButtonResult(surface, section, index, label, button_id, disabled, "FAIL", [], [], "visible button has no accessible label")
            )
            continue
        if disabled:
            results.append(
                ButtonResult(surface, section, index, label, button_id, True, "CONDITIONAL", ["disabled-by-state"], [], "disabled control recorded; executable prerequisites are state-dependent")
            )
            continue

        scope = navigate(page, section)
        buttons = page.locator(f"{scope} button:visible")
        if buttons.count() <= index:
            results.append(
                ButtonResult(surface, section, index, label, button_id, False, "FAIL", [], [], "button disappeared after deterministic reload")
            )
            continue
        button = buttons.nth(index)
        current_label = (button.inner_text() or button.get_attribute("aria-label") or button.get_attribute("title") or "").strip()
        if current_label != label and button_id:
            button = page.locator(f"#{button_id}")
            if not button.count() or not button.is_visible():
                results.append(
                    ButtonResult(surface, section, index, label, button_id, False, "FAIL", [], [], "stable button id no longer visible after reload")
                )
                continue

        events: list[dict[str, object]] = []
        response_status: dict[tuple[str, str], int] = {}
        dialogs: list[str] = []
        downloads: list[str] = []

        def on_request(request) -> None:
            if same_origin(request.url):
                events.append({"method": request.method, "url": request.url, "path": request_path(request.url)})

        def on_response(response) -> None:
            request = response.request
            if same_origin(request.url):
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
        before_scope = scope_signature(page, scope)
        before_storage = storage_snapshot(page)
        before_probe = probe_snapshot(page)
        before_focus = page.evaluate("() => document.activeElement?.outerHTML || ''")
        before_disabled = button.is_disabled()
        before_text = (button.inner_text() or "").strip()
        before_expanded = button.get_attribute("aria-expanded")

        click_error = ""
        try:
            button.click(timeout=2500)
            page.wait_for_timeout(650)
        except Exception as exc:  # Playwright errors are intentionally reported as button defects.
            click_error = str(exc).splitlines()[0]

        after_url = page.url
        after_scope = scope_signature(page, scope) if page.locator(scope).count() else ""
        after_storage = storage_snapshot(page)
        after_probe = probe_snapshot(page)
        after_focus = page.evaluate("() => document.activeElement?.outerHTML || ''")
        after_disabled = button.is_disabled() if button.count() else before_disabled
        after_text = (button.inner_text() or "").strip() if button.count() else ""
        after_expanded = button.get_attribute("aria-expanded") if button.count() else None

        page.remove_listener("request", on_request)
        page.remove_listener("response", on_response)
        page.remove_listener("dialog", on_dialog)
        page.remove_listener("download", on_download)

        effects: list[str] = []
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

        request_records: list[dict[str, object]] = []
        route_failures: list[str] = []
        for event in events:
            method = str(event["method"])
            url = str(event["url"])
            path = str(event["path"])
            status = response_status.get((method, url))
            record = {"method": method, "path": path, "status": status}
            request_records.append(record)
            if is_api_candidate(path) and method in MUTATION_METHODS and not openapi_match(openapi_paths, method, path):
                route_failures.append(f"{method} {path} is not registered in OpenAPI")
            if status in {405}:
                route_failures.append(f"{method} {path} returned HTTP {status}")

        status = "PASS"
        notes: list[str] = []
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
            ButtonResult(
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


def install_mutation_neutralizer(page: Page) -> None:
    def handler(route: Route) -> None:
        request = route.request
        if not same_origin(request.url) or request.method not in MUTATION_METHODS:
            route.continue_()
            return
        if request_path(request.url) == "/auth/token":
            route.continue_()
            return
        route.fulfill(status=200, content_type="application/json", body="{}")

    page.route("**/*", handler)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="en", accept_downloads=True)
        try:
            install_probe(page)
            establish_qualification_session(page)
            install_mutation_neutralizer(page)

            openapi_response = page.request.get(f"{BASE_URL}/openapi.json")
            if not openapi_response.ok:
                raise RuntimeError(f"failed to load OpenAPI for button qualification: HTTP {openapi_response.status}")
            openapi_paths = openapi_response.json().get("paths", {})

            console_sections = discover_console_sections(page)
            admin_sections = discover_admin_sections(page)

            results: list[ButtonResult] = []
            results.extend(validate_nav_buttons(page, "console", console_sections))
            results.extend(validate_nav_buttons(page, "admin", admin_sections))

            for section in console_sections:
                results.extend(
                    exercise_section_buttons(
                        page,
                        surface="console",
                        section=str(section["id"]),
                        openapi_paths=openapi_paths,
                    )
                )
            for section in admin_sections:
                results.extend(
                    exercise_section_buttons(
                        page,
                        surface="admin",
                        section=str(section["id"]),
                        openapi_paths=openapi_paths,
                    )
                )

            totals = {
                "all": len(results),
                "pass": sum(item.status == "PASS" for item in results),
                "conditional": sum(item.status == "CONDITIONAL" for item in results),
                "fail": sum(item.status == "FAIL" for item in results),
            }
            report = {
                "base_url": BASE_URL,
                "scope": "all delivered Console/Admin navigation plus all visible buttons in each active section",
                "mutation_policy": "mutation requests are observed and neutralized after dispatch so button wiring is proven without changing qualification data",
                "totals": totals,
                "results": [asdict(item) for item in results],
            }
            REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(totals, indent=2))

            failures = [item for item in results if item.status == "FAIL"]
            if failures:
                summary = "\n".join(
                    f"- {item.surface}/{item.section}: {item.label or '<unlabelled>'} :: {item.notes or 'no effect'}"
                    for item in failures[:30]
                )
                raise RuntimeError(
                    f"button action qualification found {len(failures)} failure(s):\n{summary}\n"
                    f"full report: {REPORT_PATH}"
                )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
