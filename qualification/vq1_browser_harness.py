from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import asdict, dataclass
from importlib.metadata import version as package_version
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import Browser, Page, sync_playwright

SOURCE_SHA = os.environ.get("VQ1_SOURCE_SHA", "unknown")
BASE_URL = os.environ.get("VQ1_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
OUTPUT_DIR = Path(os.environ.get("VQ1_OUTPUT_DIR", "artifacts/vq1"))
LOCALE = os.environ.get("VQ1_LOCALE", "en")
VQ1_USERNAME = os.environ.get("VQ1_USERNAME", "admin")
VQ1_PASSWORD = os.environ.get("VQ1_PASSWORD", "admin")

VIEWPORTS = {
    "desktop-wide": (1440, 900),
    "desktop-cockpit": (1366, 768),
    "narrow": (390, 844),
}

PUBLIC_ROUTE_SEED = [
    "/",
    "/login",
    "/plans",
    "/offer/starter",
    "/register",
    "/verify-email",
    "/pricing",
]

REQUIRED_CONSOLE_SEED = {
    "overview",
    "workflows",
    "governance",
    "telemetry",
    "reports",
    "gateway",
    "simulation",
    "settings",
}

QUARANTINED_CONSOLE_SURFACES = {"cgt", "governor"}


@dataclass
class EvidenceRow:
    source_sha: str
    browser_engine: str
    browser_version: str
    capture_tool_version: str
    route: str
    section: str
    state: str
    viewport: str
    viewport_width: int
    viewport_height: int
    locale: str
    evidence_id: str
    screenshot_path: str
    result: str
    defect_id: str
    notes: str


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip("/ ")).strip("-").lower()
    return normalized or "root"


def evidence_id(route: str, section: str, state: str, viewport: str, locale: str, counter: int) -> str:
    return (
        f"VQ1-{slug(route)}-{slug(section or 'page')}-{slug(state)}-"
        f"{slug(viewport)}-{slug(locale)}-{counter:03d}"
    ).upper()


def internal_href(href: str) -> str | None:
    if not href:
        return None
    absolute = urljoin(f"{BASE_URL}/", href)
    parsed = urlparse(absolute)
    base = urlparse(BASE_URL)
    if parsed.netloc != base.netloc:
        return None
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return path


def establish_qualification_session(page: Page) -> None:
    response = page.request.post(
        f"{BASE_URL}/auth/token",
        data={"username": VQ1_USERNAME, "password": VQ1_PASSWORD, "role": "admin"},
    )
    if not response.ok:
        raise RuntimeError(f"qualification login failed with HTTP {response.status}")
    payload = response.json()
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("qualification login response did not include access_token")

    token_literal = json.dumps(token)
    page.add_init_script(
        f"""
        (() => {{
          const token = {token_literal};
          sessionStorage.setItem('maestro_descent_gate_seen', '1');
          sessionStorage.setItem('maestro_entry_mode', 'admin');
          sessionStorage.setItem('maestro_role', 'admin');
          sessionStorage.setItem('maestro_token', token);
          sessionStorage.setItem('maestro_ui_session_started_at', new Date().toISOString());
          localStorage.removeItem('maestro_token');
          localStorage.removeItem('maestro_role');
        }})();
        """
    )


def discover_offer_routes(page: Page) -> set[str]:
    discovered: set[str] = set()
    for route in ("/plans", "/pricing"):
        page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
        for href in page.locator("a[href]").evaluate_all("els => els.map(e => e.getAttribute('href'))"):
            path = internal_href(href or "")
            if path and path.startswith("/offer/"):
                discovered.add(path.split("?", 1)[0])
    return discovered


def discover_console_sections(page: Page) -> list[dict[str, str]]:
    page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    delivered = page.locator(".nav-btn[data-page]").evaluate_all(
        "els => els.map(e => ({id: e.dataset.page || '', text: (e.innerText || '').trim(), hidden: !e.offsetParent}))"
    )
    active = [item for item in delivered if not item["hidden"]]
    active_ids = {item["id"] for item in active}
    missing = REQUIRED_CONSOLE_SEED - active_ids
    leaked = QUARANTINED_CONSOLE_SURFACES & active_ids
    if missing:
        raise RuntimeError(f"missing required Console sections: {sorted(missing)}")
    if leaked:
        raise RuntimeError(f"quarantined Console surfaces delivered as active navigation: {sorted(leaked)}")
    for surface in QUARANTINED_CONSOLE_SURFACES:
        if page.locator(f"#page-{surface}").count() != 0:
            raise RuntimeError(f"quarantined Console surface remains in delivered DOM: {surface}")
    return active


def discover_admin_sections(page: Page) -> list[dict[str, object]]:
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    top_level = page.locator(".nav-btn[data-admin-page]").evaluate_all(
        "els => els.map(e => ({id: e.dataset.adminPage || '', text: (e.innerText || '').trim(), hidden: !e.offsetParent}))"
    )
    discovered: list[dict[str, object]] = []
    for item in top_level:
        if item["hidden"]:
            continue
        selector = f'.nav-btn[data-admin-page="{item["id"]}"]'
        page.locator(selector).click()
        page.wait_for_timeout(100)
        nested = page.locator(".admin-page.active [data-am-section]:visible").evaluate_all(
            "els => els.map(e => ({id: e.dataset.amSection || '', text: (e.innerText || '').trim()}))"
        )
        discovered.append({"id": item["id"], "text": item["text"], "nested": nested})
    return discovered


def capture_page(
    page: Page,
    browser_version: str,
    route: str,
    section: str,
    viewport_name: str,
    width: int,
    height: int,
    counter: int,
) -> EvidenceRow:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
    page.wait_for_timeout(250)
    eid = evidence_id(route, section, "default-loaded", viewport_name, LOCALE, counter)
    shot = OUTPUT_DIR / "screenshots" / f"{eid}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=True)
    return EvidenceRow(
        source_sha=SOURCE_SHA,
        browser_engine="chromium",
        browser_version=browser_version,
        capture_tool_version=package_version("playwright"),
        route=route,
        section=section,
        state="default/loaded",
        viewport=viewport_name,
        viewport_width=width,
        viewport_height=height,
        locale=LOCALE,
        evidence_id=eid,
        screenshot_path=str(shot),
        result="PASS",
        defect_id="",
        notes="Automated capture completed; human visual review still required.",
    )


def capture_console_section(
    page: Page,
    browser_version: str,
    section: dict[str, str],
    viewport_name: str,
    width: int,
    height: int,
    counter: int,
) -> EvidenceRow:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{BASE_URL}/console/", wait_until="domcontentloaded")
    page.locator(f'.nav-btn[data-page="{section["id"]}"]').click()
    page.wait_for_timeout(150)
    eid = evidence_id("/console/", section["id"], "default-loaded", viewport_name, LOCALE, counter)
    shot = OUTPUT_DIR / "screenshots" / f"{eid}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shot), full_page=True)
    return EvidenceRow(
        source_sha=SOURCE_SHA,
        browser_engine="chromium",
        browser_version=browser_version,
        capture_tool_version=package_version("playwright"),
        route="/console/",
        section=section["id"],
        state="default/loaded",
        viewport=viewport_name,
        viewport_width=width,
        viewport_height=height,
        locale=LOCALE,
        evidence_id=eid,
        screenshot_path=str(shot),
        result="PASS",
        defect_id="",
        notes=f'Delivered Console navigation label: {section["text"]}. Human visual review still required.',
    )


def capture_admin_section(
    page: Page,
    browser_version: str,
    section: dict[str, object],
    viewport_name: str,
    width: int,
    height: int,
    counter: int,
) -> list[EvidenceRow]:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{BASE_URL}/admin", wait_until="domcontentloaded")
    page.locator(f'.nav-btn[data-admin-page="{section["id"]}"]').click()
    page.wait_for_timeout(150)

    targets: list[tuple[str, str]] = [(str(section["id"]), str(section["text"]))]
    for nested in section.get("nested", []):
        nested_id = str(nested["id"])
        nested_text = str(nested["text"])
        targets.append((f'{section["id"]}:{nested_id}', nested_text))

    rows: list[EvidenceRow] = []
    for offset, (target_id, target_text) in enumerate(targets):
        if ":" in target_id:
            _, nested_id = target_id.split(":", 1)
            locator = page.locator(f'.admin-page.active [data-am-section="{nested_id}"]')
            if locator.count() == 0 or not locator.first.is_visible():
                continue
            locator.first.click()
            page.wait_for_timeout(100)
        eid = evidence_id("/admin", target_id, "default-loaded", viewport_name, LOCALE, counter + offset)
        shot = OUTPUT_DIR / "screenshots" / f"{eid}.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(shot), full_page=True)
        rows.append(
            EvidenceRow(
                source_sha=SOURCE_SHA,
                browser_engine="chromium",
                browser_version=browser_version,
                capture_tool_version=package_version("playwright"),
                route="/admin",
                section=target_id,
                state="default/loaded",
                viewport=viewport_name,
                viewport_width=width,
                viewport_height=height,
                locale=LOCALE,
                evidence_id=eid,
                screenshot_path=str(shot),
                result="PASS",
                defect_id="",
                notes=f"Delivered Admin target: {target_text}. Human visual review still required.",
            )
        )
    return rows


def write_outputs(rows: list[EvidenceRow], inventory: dict[str, object], browser_version: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(EvidenceRow.__dataclass_fields__)
    with (OUTPUT_DIR / "evidence.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    (OUTPUT_DIR / "inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True), encoding="utf-8")
    metadata = {
        "source_sha": SOURCE_SHA,
        "base_url": BASE_URL,
        "browser_engine": "chromium",
        "browser_version": browser_version,
        "capture_tool": "playwright",
        "capture_tool_version": package_version("playwright"),
        "viewports": VIEWPORTS,
        "status": "AUTOMATED_DEFAULT_STATE_CAPTURE_COMPLETE_HUMAN_REVIEW_REQUIRED",
        "authority": {
            "RealStagingQualified": False,
            "ProductionAuthorityGranted": False,
        },
    }
    (OUTPUT_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def run(browser: Browser) -> None:
    page = browser.new_page(locale=LOCALE)
    establish_qualification_session(page)
    routes = set(PUBLIC_ROUTE_SEED)
    routes.update(discover_offer_routes(page))
    console_sections = discover_console_sections(page)
    admin_sections = discover_admin_sections(page)

    inventory = {
        "public_routes": sorted(routes),
        "console_sections": console_sections,
        "admin_sections": admin_sections,
        "quarantined_console_surfaces": sorted(QUARANTINED_CONSOLE_SURFACES),
    }

    rows: list[EvidenceRow] = []
    counter = 1
    browser_version = browser.version
    for viewport_name, (width, height) in VIEWPORTS.items():
        for route in sorted(routes):
            rows.append(capture_page(page, browser_version, route, "page", viewport_name, width, height, counter))
            counter += 1
        for section in console_sections:
            rows.append(
                capture_console_section(page, browser_version, section, viewport_name, width, height, counter)
            )
            counter += 1
        for section in admin_sections:
            captured = capture_admin_section(
                page, browser_version, section, viewport_name, width, height, counter
            )
            rows.extend(captured)
            counter += len(captured)

    write_outputs(rows, inventory, browser_version)


if __name__ == "__main__":
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            run(browser)
        finally:
            browser.close()
