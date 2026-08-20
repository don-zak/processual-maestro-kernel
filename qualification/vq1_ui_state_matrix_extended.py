from __future__ import annotations

import json

from playwright.sync_api import Page, sync_playwright

from vq1_browser_harness import BASE_URL, LOCALE, OUTPUT_DIR, establish_qualification_session
from vq1_ui_state_matrix import append_row, capture, next_counter, open_settings, reveal

EXTENDED_UI_STATES = [
    "permission denied",
    "billing restriction/grace",
    "billing restriction/suspended",
    "billing restriction/terminated",
]


def open_admin_marketplace(page: Page) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{BASE_URL}/admin#admin-marketplace", wait_until="domcontentloaded")
    page.wait_for_function(
        "() => window.PMK_ADMIN_NAV && typeof window.PMK_ADMIN_NAV.setActivePage === 'function'",
        timeout=4000,
    )
    page.wait_for_function(
        "() => window.PMK_ADMIN_MARKETPLACE && typeof window.PMK_ADMIN_MARKETPLACE.activateSection === 'function'",
        timeout=4000,
    )


def admin_marketplace_permission_denied(page: Page, browser_version: str, counter: int):
    pattern = "**/admin-marketplace/payment-destinations"
    page.route(
        pattern,
        lambda route: route.fulfill(
            status=403,
            content_type="application/json",
            body='{"detail":"controlled qualification authority denied"}',
        ),
    )
    try:
        open_admin_marketplace(page)
        state = page.locator('#am-payment-destination-list[data-state="error"]').filter(
            has_text="An active platform administrator authority is required"
        )
        authority = page.locator('#admin-marketplace-authority-state[data-state="denied"]')
        state.wait_for(state="attached", timeout=4000)
        authority.wait_for(state="attached", timeout=4000)
        page.evaluate(
            """
            () => {
              window.PMK_ADMIN_NAV.setActivePage('admin-marketplace');
              window.PMK_ADMIN_MARKETPLACE.activateSection('payment-destinations');
            }
            """
        )
        page.locator("#page-admin-marketplace.active").wait_for(state="visible", timeout=4000)
        state.wait_for(state="visible", timeout=4000)
        authority.wait_for(state="visible", timeout=4000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/admin",
            "admin-marketplace:payment-destinations",
            "permission denied",
            counter,
            "Controlled HTTP 403 interception proves the delivered Admin Marketplace permission-denied renderer only; the real Admin navigation and Marketplace section APIs expose the denied payment-destinations panel after authority denial. No platform authority is granted or mutated.",
        )
    finally:
        page.unroute(pattern)


def open_plan_usage(page: Page) -> None:
    open_settings(page)
    tab = page.get_by_text("Plan & usage", exact=True)
    if tab.count():
        tab.first.click()
        page.wait_for_timeout(120)


def subscription_state(
    page: Page,
    browser_version: str,
    counter: int,
    status: str,
    stage: str,
    state_name: str,
    renews_at: str | None,
    suspended_at: str | None,
):
    pattern = "**/settings/subscription"
    payload = {
        "plan": "qualification_plan",
        "status": status,
        "stage": stage,
        "renews_at": renews_at,
        "suspended_at": suspended_at,
        "seats": 1,
        "max_seats": 1,
    }
    page.route(
        pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload),
        ),
    )
    try:
        open_plan_usage(page)
        state = page.locator("#set-sub-status").filter(has_text=status)
        state.wait_for(state="visible", timeout=4000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/console/",
            "settings-subscription",
            state_name,
            counter,
            "Controlled /settings/subscription response exercises the delivered Settings subscription renderer using the public backend response contract; this is UI qualification only, not billing-provider or staging evidence.",
        )
    finally:
        page.unroute(pattern)


def update_metadata() -> None:
    metadata_path = OUTPUT_DIR / "metadata.json"
    inventory_path = OUTPUT_DIR / "inventory.json"

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    states = list(metadata.get("controlled_ui_states", []))
    for state in EXTENDED_UI_STATES:
        if state not in states:
            states.append(state)
    metadata["controlled_ui_states"] = states
    metadata["status"] = "AUTOMATED_DEFAULT_AND_CONTROLLED_UI_STATE_CAPTURE_COMPLETE_HUMAN_REVIEW_REQUIRED"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    controlled = dict(inventory.get("controlled_ui_states", {}))
    controlled["admin_marketplace"] = ["permission denied"]
    controlled["settings_subscription"] = [
        "billing restriction/grace",
        "billing restriction/suspended",
        "billing restriction/terminated",
    ]
    controlled["interception_only"] = True
    controlled["backend_or_staging_proof"] = False
    inventory["controlled_ui_states"] = controlled
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    counter = next_counter()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale=LOCALE)
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
            browser_version = browser.version
            rows = [
                admin_marketplace_permission_denied(page, browser_version, counter),
                subscription_state(
                    page,
                    browser_version,
                    counter + 1,
                    status="grace",
                    stage="grace",
                    state_name="billing restriction/grace",
                    renews_at="2026-08-27T00:00:00Z",
                    suspended_at=None,
                ),
                subscription_state(
                    page,
                    browser_version,
                    counter + 2,
                    status="suspended",
                    stage="suspended",
                    state_name="billing restriction/suspended",
                    renews_at=None,
                    suspended_at="2026-08-20T00:00:00Z",
                ),
                subscription_state(
                    page,
                    browser_version,
                    counter + 3,
                    status="terminated",
                    stage="expired",
                    state_name="billing restriction/terminated",
                    renews_at=None,
                    suspended_at="2026-08-20T00:00:00Z",
                ),
            ]
            for row in rows:
                append_row(row)
        finally:
            browser.close()
    update_metadata()
    print("captured 4 extended controlled UI state(s)")


if __name__ == "__main__":
    main()
