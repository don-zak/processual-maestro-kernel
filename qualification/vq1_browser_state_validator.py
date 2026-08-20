from __future__ import annotations

import csv
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from qualification.vq1_browser_harness import (
    BASE_URL,
    OUTPUT_DIR,
    VQ1_PASSWORD,
    VQ1_USERNAME,
    establish_qualification_session,
)

EVIDENCE_CSV = OUTPUT_DIR / "evidence.csv"


def evidence_path(route: str, section: str, state: str) -> Path:
    with EVIDENCE_CSV.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["route"] == route and row["section"] == section and row["state"] == state:
                return Path(row["screenshot_path"])
    raise RuntimeError(f"missing controlled evidence row for {route} {section} {state}")


def open_surface(page: Page, route: str, section: str) -> str:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
    page.wait_for_timeout(200)
    if route == "/console/":
        page.locator(f'.nav-btn[data-page="{section}"]').click()
        page.wait_for_timeout(150)
        return f"#page-{section}"
    page.locator(f'.nav-btn[data-admin-page="{section}"]').click()
    page.wait_for_timeout(150)
    return f"#page-admin-{section}"


def validate_scroll(page: Page, route: str, section: str) -> None:
    open_surface(page, route, section)
    scroll_selector = "#content" if route == "/console/" else ".admin-page.active"
    metrics = page.locator(scroll_selector).evaluate(
        """
        el => {
          const before = el.scrollTop;
          const maximum = Math.max(0, el.scrollHeight - el.clientHeight);
          el.scrollTop = maximum;
          return {
            before,
            after: el.scrollTop,
            clientHeight: el.clientHeight,
            scrollHeight: el.scrollHeight,
            maximum,
          };
        }
        """
    )
    page.wait_for_timeout(100)
    if metrics["maximum"] < 16 or metrics["after"] < 8:
        raise RuntimeError(
            f"controlled overflow did not produce real scroll for {route} {section}: {metrics}"
        )
    shot = evidence_path(route, section, "long-content/overflow")
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=False)


def validate_focus(page: Page, route: str, section: str) -> None:
    surface_selector = open_surface(page, route, section)
    page.evaluate("document.activeElement && document.activeElement.blur()")
    focused = False
    active_summary = ""
    for _ in range(80):
        page.keyboard.press("Tab")
        state = page.evaluate(
            """
            selector => {
              const surface = document.querySelector(selector);
              const el = document.activeElement;
              if (!surface || !el || el === document.body) return {inside: false, summary: ''};
              return {
                inside: surface.contains(el),
                summary: [el.tagName, el.id || '', el.getAttribute('name') || '', el.textContent || '']
                  .join(' ')
                  .trim()
                  .slice(0, 180),
              };
            }
            """,
            surface_selector,
        )
        if state["inside"]:
            focused = True
            active_summary = state["summary"]
            break
    if not focused:
        raise RuntimeError(f"keyboard focus never entered active surface {route} {section}")
    shot = evidence_path(route, section, "focus/keyboard-visible")
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=False)
    print(f"validated focus inside {route} {section}: {active_summary}")


def validate_rtl(page: Page, route: str, section: str) -> None:
    surface_selector = open_surface(page, route, section)
    page.evaluate(
        """
        () => {
          document.documentElement.setAttribute('dir', 'rtl');
          document.documentElement.setAttribute('lang', 'ar');
          document.body.setAttribute('dir', 'rtl');
        }
        """
    )
    direction = page.locator(surface_selector).evaluate("el => getComputedStyle(el).direction")
    if direction != "rtl":
        raise RuntimeError(f"controlled RTL direction did not apply to {route} {section}: {direction}")
    shot = evidence_path(route, section, "localization/RTL")
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=False)


def main() -> None:
    if not EVIDENCE_CSV.exists():
        raise RuntimeError(f"VQ evidence CSV not found: {EVIDENCE_CSV}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="en")
        try:
            establish_qualification_session(page)
            for route, section in (("/console/", "settings"), ("/admin", "api-keys")):
                validate_scroll(page, route, section)
                validate_focus(page, route, section)
                validate_rtl(page, route, section)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
