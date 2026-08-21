from __future__ import annotations

import csv
import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from vq1_browser_harness import BASE_URL, OUTPUT_DIR, establish_qualification_session


EVIDENCE_CSV = OUTPUT_DIR / "evidence.csv"
SETTINGS_PAYLOAD = {
    "general": {"language": "en", "refresh_interval": 30, "timezone": "UTC"},
    "subscription": {
        "plan": "enterprise_integration_starter",
        "status": "active",
        "stage": "active",
        "renews_at": "2026-09-20T00:00:00Z",
        "suspended_at": None,
        "seats": 1,
        "max_seats": 1,
    },
}
BILLING_STATEMENTS_PAYLOAD = {"statements": []}
API_KEY_INTEGRATION_PAYLOAD = {
    "enabled": False,
    "plan_id": "enterprise_integration_starter",
    "operational_profiles": [],
    "production_allowed": False,
    "runtime_connector_approved": False,
}
AUTH_ME_PAYLOAD = {
    "sub": "admin",
    "role": "admin",
    "client_id": "admin",
    "organization_name": "Qualification Enterprise",
}
INTEGRATION_CASES_PAYLOAD = {"cases": []}
CLIENT_REQUESTS_PAYLOAD = {"latest_requests": []}


def fulfill_json(route, payload: object) -> None:
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(payload),
    )


def install_clean_console_routes(page: Page) -> None:
    page.route(
        "**/settings",
        lambda route: fulfill_json(route, SETTINGS_PAYLOAD),
    )
    page.route(
        "**/settings/subscription",
        lambda route: fulfill_json(route, SETTINGS_PAYLOAD["subscription"]),
    )
    page.route(
        "**/billing/statements",
        lambda route: fulfill_json(route, BILLING_STATEMENTS_PAYLOAD),
    )
    page.route(
        "**/settings/api-key-integration",
        lambda route: fulfill_json(route, API_KEY_INTEGRATION_PAYLOAD),
    )
    page.route(
        "**/auth/me",
        lambda route: fulfill_json(route, AUTH_ME_PAYLOAD),
    )
    page.route(
        "**/settings/client/integration-cases",
        lambda route: fulfill_json(route, INTEGRATION_CASES_PAYLOAD),
    )
    page.route(
        "**/settings/client-requests",
        lambda route: fulfill_json(route, CLIENT_REQUESTS_PAYLOAD),
    )


def default_rows() -> list[dict[str, str]]:
    with EVIDENCE_CSV.open(newline="", encoding="utf-8") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["state"] == "default/loaded"
            and (
                (
                    row["route"] == "/console/"
                    and row["section"] in {"settings", "institution"}
                )
                or (row["route"] == "/admin" and row["section"] == "home")
            )
        ]

    console_sections = {
        row["section"] for row in rows if row["route"] == "/console/"
    }
    missing_console = {"settings", "institution"} - console_sections
    if missing_console:
        raise RuntimeError(
            "missing clean Console default/loaded evidence rows for: "
            + ", ".join(sorted(missing_console))
        )

    if not any(
        row["route"] == "/admin" and row["section"] == "home"
        for row in rows
    ):
        raise RuntimeError("missing clean Admin Home default/loaded evidence rows")

    return rows


def reset_ui_scroll(page: Page) -> None:
    page.evaluate(
        """
        () => {
          window.scrollTo(0, 0);
          document.documentElement.scrollTop = 0;
          document.body.scrollTop = 0;
          ['#content', '#main', '.page.active', '.admin-page.active'].forEach((selector) => {
            document.querySelectorAll(selector).forEach((element) => {
              element.scrollTop = 0;
              element.scrollLeft = 0;
            });
          });
        }
        """
    )


def assert_clean_default_state(
    page: Page,
    *,
    section: str,
    width: int,
    height: int,
) -> None:
    messages = (
        "Failed to load client settings",
        "Subscription access is temporarily unavailable",
        "Subscription status unavailable",
        "Operational case data is unavailable until subscription verification recovers",
        "Case registry is unavailable until subscription verification recovers",
    )
    for message in messages:
        error = page.get_by_text(message, exact=False)
        if error.count() and error.first.is_visible():
            raise RuntimeError(
                f"{section} default evidence contains unrelated dependency error "
                f"at {width}x{height}: {message}"
            )

    tour = page.get_by_text("Choose Tour Language", exact=True)
    if tour.count() and tour.first.is_visible():
        raise RuntimeError(
            f"{section} default evidence is obstructed by guided-tour language modal "
            f"at {width}x{height}"
        )


def open_console_section(
    page: Page,
    *,
    section: str,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    page.locator(f'.nav-btn[data-page="{section}"]').click()
    page.wait_for_timeout(400)
    reset_ui_scroll(page)
    assert_clean_default_state(
        page,
        section=section,
        width=width,
        height=height,
    )


def open_admin_home(
    page: Page,
    *,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    page.locator('.nav-btn[data-admin-page="home"]').click()
    page.locator("#admin-home-canonical-surface").wait_for(
        state="visible",
        timeout=5000,
    )
    # Match the Admin Home readiness contract already exercised by the VQ
    # browser-state validator rather than relying on an optional summary host.
    page.wait_for_timeout(2400)
    page.locator("#admin-integration-readiness-tracking-summary-card").wait_for(
        state="visible",
        timeout=5000,
    )
    reset_ui_scroll(page)


def install_tour_suppression(page: Page) -> None:
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


def main() -> None:
    if not EVIDENCE_CSV.exists():
        raise RuntimeError(f"VQ evidence CSV not found: {EVIDENCE_CSV}")

    rows = default_rows()
    refreshed: dict[str, int] = {"settings": 0, "institution": 0, "admin-home": 0}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        console_page = browser.new_page(locale="en")
        admin_page = browser.new_page(locale="en")
        try:
            establish_qualification_session(console_page)
            establish_qualification_session(admin_page)
            install_tour_suppression(console_page)
            install_tour_suppression(admin_page)
            install_clean_console_routes(console_page)

            for row in rows:
                width = int(row["viewport_width"])
                height = int(row["viewport_height"])
                if row["route"] == "/console/":
                    section = row["section"]
                    capture_page = console_page
                    open_console_section(
                        capture_page,
                        section=section,
                        width=width,
                        height=height,
                    )
                    refreshed[section] += 1
                    label = section
                else:
                    capture_page = admin_page
                    open_admin_home(capture_page, width=width, height=height)
                    refreshed["admin-home"] += 1
                    label = "admin-home"

                shot = Path(row["screenshot_path"])
                shot.parent.mkdir(parents=True, exist_ok=True)
                capture_page.screenshot(path=str(shot), full_page=True)
                print(
                    f"refreshed clean {label} default evidence: "
                    f"{row['viewport']} {width}x{height} -> {shot}"
                )
        finally:
            browser.close()

    print(
        "refreshed clean default/loaded evidence: "
        + ", ".join(
            f"{section}={count}"
            for section, count in sorted(refreshed.items())
        )
    )


if __name__ == "__main__":
    main()
