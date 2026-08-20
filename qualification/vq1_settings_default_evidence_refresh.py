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
        "plan": "qualification_plan",
        "status": "active",
        "stage": "active",
        "renews_at": "2026-09-20T00:00:00Z",
        "suspended_at": None,
        "seats": 1,
        "max_seats": 1,
    },
}


def install_clean_settings_routes(page: Page) -> None:
    page.route(
        "**/settings",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(SETTINGS_PAYLOAD),
        ),
    )
    page.route(
        "**/settings/subscription",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(SETTINGS_PAYLOAD["subscription"]),
        ),
    )


def default_rows() -> list[dict[str, str]]:
    with EVIDENCE_CSV.open(newline="", encoding="utf-8") as handle:
        rows = [
            row
            for row in csv.DictReader(handle)
            if row["route"] == "/console/"
            and row["section"] == "settings"
            and row["state"] == "default/loaded"
        ]
    if not rows:
        raise RuntimeError("missing Settings default/loaded evidence rows")
    return rows


def open_settings(page: Page, width: int, height: int) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    page.locator('.nav-btn[data-page="settings"]').click()
    page.wait_for_timeout(250)
    error = page.get_by_text("Failed to load client settings", exact=False)
    if error.count() and error.first.is_visible():
        raise RuntimeError(
            f"Settings default evidence still contains dependency error at {width}x{height}"
        )


def main() -> None:
    if not EVIDENCE_CSV.exists():
        raise RuntimeError(f"VQ evidence CSV not found: {EVIDENCE_CSV}")

    rows = default_rows()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="en")
        try:
            establish_qualification_session(page)
            install_clean_settings_routes(page)
            for row in rows:
                width = int(row["width"])
                height = int(row["height"])
                open_settings(page, width, height)
                shot = Path(row["screenshot_path"])
                shot.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(shot), full_page=True)
                print(
                    "refreshed clean Settings default evidence: "
                    f"{row['viewport']} {width}x{height} -> {shot}"
                )
        finally:
            browser.close()

    print(f"refreshed {len(rows)} Settings default/loaded evidence row(s)")


if __name__ == "__main__":
    main()
