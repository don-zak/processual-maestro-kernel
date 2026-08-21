from __future__ import annotations

from playwright.sync_api import sync_playwright

from vq1_browser_harness import BASE_URL, establish_qualification_session

TAB_KEYS = ["operations", "account", "usage", "integration", "support"]


def main() -> None:
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
            page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
            page.wait_for_timeout(500)
            page.locator('.nav-btn[data-page="settings"]').click()
            page.wait_for_timeout(900)

            for key in TAB_KEYS:
                tab = page.locator(f'[data-sl18-tab="{key}"]')
                panel = page.locator(f'[data-sl18-panel="{key}"]')
                if tab.count() != 1:
                    raise RuntimeError(f"Settings tab missing or duplicated: {key}")
                if panel.count() != 1:
                    raise RuntimeError(f"Settings panel missing or duplicated: {key}")

                tab.click()
                page.wait_for_timeout(180)

                if tab.get_attribute("aria-selected") != "true":
                    raise RuntimeError(f"Settings tab did not become selected: {key}")
                if panel.get_attribute("aria-hidden") == "true" or panel.is_hidden():
                    raise RuntimeError(f"Settings panel did not become visible: {key}")
                if panel.get_attribute("data-tab-activation-proven") != "true":
                    raise RuntimeError(f"Settings runtime activation marker missing: {key}")

                visible_count = page.locator(
                    '#page-settings [data-sl18-panel]:visible'
                ).count()
                if visible_count != 1:
                    raise RuntimeError(
                        f"Settings must expose exactly one visible panel after {key}; got {visible_count}"
                    )

                active_key = page.locator('#page-settings').get_attribute(
                    'data-active-settings-tab'
                )
                if active_key != key:
                    raise RuntimeError(
                        f"Settings active tab marker mismatch: expected {key}, got {active_key}"
                    )

                print(f"PASS settings tab: {key}")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
