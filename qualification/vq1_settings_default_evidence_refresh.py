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
            if row["route"] == "/console/"
            and row["section"] in {"settings", "institution"}
            and row["state"] == "default/loaded"
        ]
    sections = {row["section"] for row in rows}
    missing = {"settings", "institution"} - sections
    if missing:
        raise RuntimeError(
            "missing clean Console default/loaded evidence rows for: "
            + ", ".join(sorted(missing))
        )
    return rows


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
    assert_clean_default_state(
        page,
        section=section,
        width=width,
        height=height,
    )


def main() -> None:
    if not EVIDENCE_CSV.exists():
        raise RuntimeError(f"VQ evidence CSV not found: {EVIDENCE_CSV}")

    rows = default_rows()
    refreshed: dict[str, int] = {"settings": 0, "institution": 0}
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
            install_clean_console_routes(page)
            for row in rows:
                section = row["section"]
                width = int(row["viewport_width"])
                height = int(row["viewport_height"])
                open_console_section(
                    page,
                    section=section,
                    width=width,
                    height=height,
                )
                shot = Path(row["screenshot_path"])
                shot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot), full_page=True)
                refreshed[section] += 1
                print(
                    f"refreshed clean {section} default evidence: "
                    f"{row['viewport']} {width}x{height} -> {shot}"
                )
        finally:
            browser.close()

    print(
        "refreshed clean Console default/loaded evidence: "
        + ", ".join(
            f"{section}={count}"
            for section, count in sorted(refreshed.items())
        )
    )


if __name__ == "__main__":
    main()
