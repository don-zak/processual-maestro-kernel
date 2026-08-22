from __future__ import annotations

import csv
import json
from dataclasses import asdict
from importlib.metadata import version as package_version
from pathlib import Path

from playwright.sync_api import Locator, Page, Route, sync_playwright

from vq1_browser_harness import (
    BASE_URL,
    LOCALE,
    OUTPUT_DIR,
    SOURCE_SHA,
    EvidenceRow,
    establish_qualification_session,
    evidence_id,
)

EVIDENCE_CSV = OUTPUT_DIR / "evidence.csv"
NARROW = (390, 844)
CONTROLLED_UI_STATES = [
    "loading",
    "empty/no-data",
    "unavailable/fail-closed",
    "validation error",
    "success",
]


def next_counter() -> int:
    if not EVIDENCE_CSV.exists():
        raise RuntimeError(f"VQ evidence CSV not found: {EVIDENCE_CSV}")
    with EVIDENCE_CSV.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle)) + 1


def append_row(row: EvidenceRow) -> None:
    fields = list(EvidenceRow.__dataclass_fields__)
    with EVIDENCE_CSV.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writerow(asdict(row))


def reveal(locator: Locator) -> None:
    locator.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
    locator.page.wait_for_timeout(100)


def capture(
    page: Page,
    browser_version: str,
    route: str,
    section: str,
    state: str,
    counter: int,
    notes: str,
) -> EvidenceRow:
    width, height = NARROW
    eid = evidence_id(route, section, state, "narrow", LOCALE, counter)
    shot = OUTPUT_DIR / "screenshots" / f"{eid}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=False)
    return EvidenceRow(
        source_sha=SOURCE_SHA,
        browser_engine="chromium",
        browser_version=browser_version,
        capture_tool_version=package_version("playwright"),
        route=route,
        section=section,
        state=state,
        viewport="narrow",
        viewport_width=width,
        viewport_height=height,
        locale=LOCALE,
        evidence_id=eid,
        screenshot_path=str(shot),
        result="PASS",
        defect_id="",
        notes=notes,
    )


def open_settings(page: Page) -> None:
    page.set_viewport_size({"width": NARROW[0], "height": NARROW[1]})
    page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
    page.locator('.nav-btn[data-page="settings"]').click()
    page.wait_for_timeout(120)


def billing_loading(page: Page, browser_version: str, counter: int) -> EvidenceRow:
    pending: list[Route] = []

    def hold(route: Route) -> None:
        pending.append(route)

    pattern = "**/billing/statements"
    page.route(pattern, hold)
    try:
        open_settings(page)
        state = page.locator("#settings-billing-statements-root .mbs-empty").filter(
            has_text="Loading billing statements"
        )
        state.wait_for(state="visible", timeout=4000)
        reveal(state)
        row = capture(
            page,
            browser_version,
            "/console/",
            "settings-billing",
            "loading",
            counter,
            "Controlled interception holds GET /billing/statements pending; this proves the delivered Settings Billing loading renderer only.",
        )
        for route in pending:
            try:
                route.fulfill(status=200, content_type="application/json", body='{"statements":[]}')
            except Exception:
                pass
        return row
    finally:
        page.unroute(pattern)


def billing_empty(page: Page, browser_version: str, counter: int) -> EvidenceRow:
    pattern = "**/billing/statements"
    page.route(
        pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"statements":[]}',
        ),
    )
    try:
        open_settings(page)
        state = page.get_by_text("No billing statements have been issued yet.", exact=False)
        state.wait_for(state="visible", timeout=4000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/console/",
            "settings-billing",
            "empty/no-data",
            counter,
            "Controlled interception returns an empty statements collection; this proves the delivered no-data renderer only.",
        )
    finally:
        page.unroute(pattern)


def billing_unavailable(page: Page, browser_version: str, counter: int) -> EvidenceRow:
    pattern = "**/billing/statements"
    page.route(
        pattern,
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"Billing statements are temporarily unavailable for qualification."}',
        ),
    )
    try:
        open_settings(page)
        state = page.locator("#settings-billing-statements-root .mbs-error")
        state.wait_for(state="visible", timeout=4000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/console/",
            "settings-billing",
            "unavailable/fail-closed",
            counter,
            "Controlled HTTP 503 interception proves the delivered Settings Billing fail-closed error renderer; it is not external-service or staging evidence.",
        )
    finally:
        page.unroute(pattern)


def configure_registration(page: Page) -> None:
    page.route(
        "**/auth/registration/config",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"password_min_length":12,"password_max_length":1024,"registration_modes":["individual","organization"]}',
        ),
    )


def open_register(page: Page) -> None:
    page.set_viewport_size({"width": NARROW[0], "height": NARROW[1]})
    page.goto(f"{BASE_URL}/register", wait_until="domcontentloaded")
    page.wait_for_timeout(120)


def fill_valid_registration(page: Page) -> None:
    page.locator("#registration-full-name").fill("Qualification User")
    page.locator("#registration-email").fill("qualification@example.invalid")
    page.locator("#registration-password").fill("qualification-pass-2026")
    page.locator("#registration-terms").check()


def register_validation_error(page: Page, browser_version: str, counter: int) -> EvidenceRow:
    configure_registration(page)
    try:
        open_register(page)
        page.locator("#registration-submit").click()
        state = page.locator('#registration-status[data-state="error"]').filter(
            has_text="Review the highlighted registration fields"
        )
        state.wait_for(state="visible", timeout=3000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/register",
            "registration-form",
            "validation error",
            counter,
            "Native form validity drives the real registration error renderer; no backend registration request is sent.",
        )
    finally:
        page.unroute("**/auth/registration/config")


def register_unavailable(page: Page, browser_version: str, counter: int) -> EvidenceRow:
    configure_registration(page)
    endpoint = f"{BASE_URL}/auth/register"
    page.route(
        endpoint,
        lambda route: route.fulfill(
            status=503,
            content_type="application/json",
            body='{"detail":"controlled qualification unavailable"}',
        ),
    )
    try:
        open_register(page)
        fill_valid_registration(page)
        page.locator("#registration-submit").click()
        state = page.locator('#registration-status[data-state="error"]').filter(
            has_text="Registration service is temporarily unavailable"
        )
        state.wait_for(state="visible", timeout=3000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/register",
            "registration-form",
            "unavailable/fail-closed",
            counter,
            "Controlled HTTP 503 interception proves the delivered registration unavailable renderer; no registration is created.",
        )
    finally:
        page.unroute(endpoint)
        page.unroute("**/auth/registration/config")


def register_success(page: Page, browser_version: str, counter: int) -> EvidenceRow:
    configure_registration(page)
    endpoint = f"{BASE_URL}/auth/register"
    page.route(
        endpoint,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body='{"status":"accepted"}',
        ),
    )
    try:
        open_register(page)
        fill_valid_registration(page)
        page.locator("#registration-submit").click()
        state = page.locator('#registration-status[data-state="success"]').filter(
            has_text="Registration request accepted"
        )
        state.wait_for(state="visible", timeout=3000)
        reveal(state)
        return capture(
            page,
            browser_version,
            "/register",
            "registration-form",
            "success",
            counter,
            "Controlled HTTP 200 interception proves the delivered registration accepted renderer only; no identity, subscription, entitlement, quota, or checkout is created.",
        )
    finally:
        page.unroute(endpoint)
        page.unroute("**/auth/registration/config")


def update_metadata() -> None:
    metadata_path = OUTPUT_DIR / "metadata.json"
    inventory_path = OUTPUT_DIR / "inventory.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["controlled_ui_states"] = CONTROLLED_UI_STATES
    metadata["status"] = "AUTOMATED_DEFAULT_AND_CONTROLLED_UI_STATE_CAPTURE_COMPLETE_HUMAN_REVIEW_REQUIRED"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["controlled_ui_states"] = {
        "viewport": "narrow",
        "settings_billing": ["loading", "empty/no-data", "unavailable/fail-closed"],
        "registration_form": ["validation error", "unavailable/fail-closed", "success"],
        "interception_only": True,
        "backend_or_staging_proof": False,
    }
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    counter = next_counter()
    rows: list[EvidenceRow] = []
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
            captures = (
                billing_loading,
                billing_empty,
                billing_unavailable,
                register_validation_error,
                register_unavailable,
                register_success,
            )
            for offset, capture_fn in enumerate(captures):
                row = capture_fn(page, browser_version, counter + offset)
                append_row(row)
                rows.append(row)
        finally:
            browser.close()
    update_metadata()
    print(f"captured {len(rows)} controlled UI state(s)")


if __name__ == "__main__":
    main()
