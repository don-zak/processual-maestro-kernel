from __future__ import annotations

import csv
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from vq1_browser_harness import BASE_URL, OUTPUT_DIR, establish_qualification_session

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
    surface_selector = open_surface(page, route, section)
    metrics = page.evaluate(
        """
        selector => {
          const surface = document.querySelector(selector);
          if (!surface) return null;
          const candidates = [];
          let node = surface;
          while (node && node !== document.documentElement) {
            if (node instanceof HTMLElement) {
              const style = getComputedStyle(node);
              const maximum = Math.max(0, node.scrollHeight - node.clientHeight);
              const scrollable = maximum > 0 && /(auto|scroll|overlay)/.test(style.overflowY);
              candidates.push({ node, maximum, overflowY: style.overflowY, scrollable });
            }
            node = node.parentElement;
          }
          const body = document.scrollingElement || document.documentElement;
          if (body) {
            candidates.push({
              node: body,
              maximum: Math.max(0, body.scrollHeight - body.clientHeight),
              overflowY: getComputedStyle(document.documentElement).overflowY,
              scrollable: Math.max(0, body.scrollHeight - body.clientHeight) > 0,
            });
          }
          const chosen = candidates.find(item => item.scrollable) || candidates.find(item => item.maximum > 0);
          if (!chosen) return { found: false, candidates: candidates.map(item => ({ maximum: item.maximum, overflowY: item.overflowY })) };
          const before = chosen.node.scrollTop;
          chosen.node.scrollTop = chosen.maximum;
          return {
            found: true,
            before,
            after: chosen.node.scrollTop,
            clientHeight: chosen.node.clientHeight,
            scrollHeight: chosen.node.scrollHeight,
            maximum: chosen.maximum,
            overflowY: chosen.overflowY,
            tag: chosen.node.tagName,
            id: chosen.node.id || '',
            className: String(chosen.node.className || ''),
          };
        }
        """,
        surface_selector,
    )
    page.wait_for_timeout(120)
    if not metrics or not metrics.get("found") or metrics["maximum"] < 16 or metrics["after"] < 8:
        raise RuntimeError(
            f"controlled overflow did not produce real scroll for {route} {section}: {metrics}"
        )
    shot = evidence_path(route, section, "long-content/overflow")
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=False)
    print(
        f"validated scroll inside {route} {section}: "
        f"{metrics['tag']}#{metrics['id']}.{metrics['className']} after={metrics['after']} max={metrics['maximum']}"
    )


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


def collapsed_screenshot_path(route: str, section: str) -> Path:
    route_slug = "console" if route == "/console/" else "admin"
    section_slug = section.replace("/", "-").replace("_", "-")
    return OUTPUT_DIR / "screenshots" / f"VQ1-VALIDATED-{route_slug}-{section_slug}-LONG-CARD-COLLAPSED-NARROW-EN.png"


def validate_collapsible_cards(page: Page, route: str, section: str) -> None:
    surface_selector = open_surface(page, route, section)
    page.wait_for_timeout(2100)

    if route == "/console/" and section == "settings":
        billing_hero = page.locator(f"{surface_selector} #settings-billing-statements-root .mbs-hero:visible")
        if billing_hero.count():
            hero_height = billing_hero.first.evaluate("el => el.scrollHeight")
            if hero_height >= 420 and billing_hero.first.get_attribute("data-pmk-long-card") != "true":
                raise RuntimeError(
                    f"long Settings billing hero is not collapsible: scrollHeight={hero_height}"
                )

    cards = page.locator(f'{surface_selector} [data-pmk-long-card="true"]:visible')
    count = cards.count()
    if count < 1:
        raise RuntimeError(f"no collapsible long card detected for {route} {section}")

    tested = min(count, 12)
    for index in range(tested):
        card = cards.nth(index)
        button = card.locator(':scope > .pmk-long-card-tools > .pmk-long-card-toggle')
        if button.count() != 1:
            raise RuntimeError(f"long card missing direct collapse control for {route} {section} index={index}")

        before_height = card.evaluate("el => el.getBoundingClientRect().height")
        button.click()
        page.wait_for_timeout(100)
        after_height = card.evaluate("el => el.getBoundingClientRect().height")
        collapsed = card.get_attribute('data-pmk-collapsed')
        expanded = button.get_attribute('aria-expanded')
        if collapsed != 'true' or expanded != 'false':
            raise RuntimeError(
                f"collapse control state failed for {route} {section} index={index}: "
                f"collapsed={collapsed} aria-expanded={expanded}"
            )
        minimum_shrink = max(64.0, before_height * 0.20)
        if before_height - after_height < minimum_shrink:
            raise RuntimeError(
                f"collapse did not materially reduce card height for {route} {section} index={index}: "
                f"before={before_height:.1f} after={after_height:.1f} required_shrink={minimum_shrink:.1f}"
            )

        if index == 0:
            shot = collapsed_screenshot_path(route, section)
            shot.parent.mkdir(parents=True, exist_ok=True)
            card.scroll_into_view_if_needed()
            page.wait_for_timeout(80)
            page.screenshot(path=str(shot), full_page=False)

        button.click()
        page.wait_for_timeout(100)
        restored_height = card.evaluate("el => el.getBoundingClientRect().height")
        collapsed = card.get_attribute('data-pmk-collapsed')
        expanded = button.get_attribute('aria-expanded')
        if collapsed != 'false' or expanded != 'true':
            raise RuntimeError(
                f"expand control state failed for {route} {section} index={index}: "
                f"collapsed={collapsed} aria-expanded={expanded}"
            )
        if restored_height < after_height + minimum_shrink * 0.75:
            raise RuntimeError(
                f"expand did not restore long-card height for {route} {section} index={index}: "
                f"before={before_height:.1f} collapsed={after_height:.1f} restored={restored_height:.1f}"
            )

    print(f"validated {tested}/{count} collapsible long card(s) for {route} {section}")


def main() -> None:
    if not EVIDENCE_CSV.exists():
        raise RuntimeError(f"VQ evidence CSV not found: {EVIDENCE_CSV}")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="en")
        try:
            establish_qualification_session(page)
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
            for route, section in (("/console/", "settings"), ("/admin", "api-keys")):
                validate_scroll(page, route, section)
                validate_focus(page, route, section)
                validate_rtl(page, route, section)
            for route, section in (("/console/", "settings"), ("/admin", "home"), ("/admin", "api-keys")):
                validate_collapsible_cards(page, route, section)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
