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
    "mfa challenge",
    "selected commercial offer",
]

REQUIRED_FALSE_AUTHORITY_FLAGS = (
    "RepositoryReconciliationComplete",
    "GeneralPackagingComplete",
    "PrivateRuntimeAuthorityGranted",
    "runtime_connector_approved",
    "provider_sandbox_proven",
    "operator_network_qos_proven",
    "RealStagingQualified",
    "ProductionAuthorityGranted",
)


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
              window.PMK_ADMIN_LAYOUT?.clean?.();
              window.PMK_ADMIN_NAV.setActivePage('admin-marketplace');
              window.PMK_ADMIN_MARKETPLACE.activateSection('payment-destinations');
            }
            """
        )
        page.locator("#page-admin-marketplace.active").wait_for(state="visible", timeout=4000)
        state.wait_for(state="visible", timeout=4000)
        authority.wait_for(state="visible", timeout=4000)
        leaked = page.locator(
            '#admin-integration-readiness-tracking-summary-host:visible, '
            '#admin-integration-readiness-case-management-host:visible, '
            '#admin-integration-claim-keys-host:visible, '
            '#admin-integration-readiness-operator-package-host:visible'
        )
        if leaked.count():
            raise RuntimeError("Admin Marketplace permission-denied evidence contains cross-page owned surfaces")
        reveal(state)
        return capture(
            page,
            browser_version,
            "/admin",
            "admin-marketplace:payment-destinations",
            "permission denied",
            counter,
            "Controlled HTTP 403 interception proves the delivered Admin Marketplace permission-denied renderer only; the real Admin layout, navigation, and Marketplace section APIs expose the denied payment-destinations panel after authority denial. No platform authority is granted or mutated.",
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
    subscription_pattern = "**/settings/subscription"
    settings_pattern = "**/settings"
    payload = {
        "plan": "qualification_plan",
        "status": status,
        "stage": stage,
        "renews_at": renews_at,
        "suspended_at": suspended_at,
        "seats": 1,
        "max_seats": 1,
    }
    settings_payload = {
        "general": {
            "language": "en",
            "refresh_interval": 30,
            "timezone": "UTC",
        },
        "subscription": payload,
    }
    page.route(
        settings_pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(settings_payload),
        ),
    )
    page.route(
        subscription_pattern,
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
            "Controlled /settings and /settings/subscription responses exercise the delivered Settings subscription renderer using the public response contract while isolating unrelated dependencies; this is UI qualification only, not billing-provider or staging evidence.",
        )
    finally:
        page.unroute(subscription_pattern)
        page.unroute(settings_pattern)


def login_mfa_challenge(page: Page, browser_version: str, counter: int):
    login_pattern = "**/auth/login"
    status_pattern = "**/auth/mfa/status"
    page.route(
        login_pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "mfa_required": True,
                    "access_token": "qualification-mfa-token-0123456789-0123456789-0123456789",
                    "csrf_token": "qualification-csrf-token",
                }
            ),
        ),
    )
    page.route(
        status_pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "enabled": True,
                    "pending_enrollment": False,
                    "recovery_codes_remaining": 8,
                    "step_up_satisfied": False,
                }
            ),
        ),
    )
    try:
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{BASE_URL}/login?mode=user", wait_until="domcontentloaded")
        page.locator("#tab-user").click()
        page.locator("#login-username").fill("qualification@example.invalid")
        page.locator("#login-password").fill("qualification-pass-2026")
        page.locator("#login-btn").click()

        challenge = page.locator("#identity-mfa-challenge")
        challenge.wait_for(state="visible", timeout=4000)
        page.locator("#identity-mfa-code").wait_for(state="visible", timeout=4000)

        if page.locator("#login-fields:visible").count():
            raise RuntimeError("MFA challenge left primary login fields visible")
        if page.locator("#login-btn:visible").count():
            raise RuntimeError("MFA challenge left the primary login button visible")
        if page.locator(".tab-row:visible").count():
            raise RuntimeError("MFA challenge left role tabs visible")
        if page.locator("#login-commercial-actions:visible").count():
            raise RuntimeError("MFA challenge left commercial access actions visible")

        layout = page.locator(".card").evaluate(
            """
            (card) => ({
              top: card.getBoundingClientRect().top,
              bottom: card.getBoundingClientRect().bottom,
              height: card.getBoundingClientRect().height,
              viewport: window.innerHeight,
              scrollHeight: card.scrollHeight
            })
            """
        )
        if layout["top"] < 0 or layout["bottom"] > layout["viewport"]:
            raise RuntimeError(f"MFA challenge card escapes viewport: {layout}")
        if layout["scrollHeight"] > layout["height"] + 2:
            raise RuntimeError(f"MFA challenge card internally overflows: {layout}")

        reveal(challenge)
        return capture(
            page,
            browser_version,
            "/login?mode=user",
            "mfa-challenge",
            "mfa challenge",
            counter,
            "Controlled /auth/login and /auth/mfa/status interceptions exercise the delivered MFA-required path with an existing factor, without using a real MFA secret. Primary login fields, role tabs, and commercial access actions must be replaced rather than compressed into the card. This is UI proof only.",
        )
    finally:
        page.unroute(status_pattern)
        page.unroute(login_pattern)


def registration_selected_offer(page: Page, browser_version: str, counter: int):
    catalog_pattern = "**/billing/public-plan-journey"
    config_pattern = "**/auth/registration/config"
    catalog = {
        "plans": [
            {
                "plan_id": "starter",
                "display_name": "Starter",
                "monthly_price_usd": 49,
                "annual_price_usd": 490,
            }
        ]
    }
    page.route(
        catalog_pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(catalog),
        ),
    )
    page.route(
        config_pattern,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                {
                    "password_min_length": 12,
                    "password_max_length": 1024,
                    "registration_modes": ["individual", "organization"],
                }
            ),
        ),
    )
    try:
        page.set_viewport_size({"width": 390, "height": 844})
        route = "/register?plan_id=starter&billing_period=monthly"
        page.goto(f"{BASE_URL}{route}", wait_until="domcontentloaded")
        context = page.locator("#registration-plan-context")
        context.wait_for(state="visible", timeout=4000)
        page.locator("#registration-plan-name").filter(has_text="Starter").wait_for(
            state="visible", timeout=4000
        )
        page.locator("#registration-plan-billing").filter(has_text="Monthly").wait_for(
            state="visible", timeout=4000
        )
        page.locator("#registration-plan-price").filter(has_text="$49 / month").wait_for(
            state="visible", timeout=4000
        )
        note = page.locator("#registration-plan-note").filter(
            has_text="Registration alone does not activate payment, entitlement, quota, or checkout"
        )
        note.wait_for(state="visible", timeout=4000)
        reveal(context)
        return capture(
            page,
            browser_version,
            route,
            "registration-selected-offer",
            "selected commercial offer",
            counter,
            "Controlled public-plan catalog response proves that the selected Starter monthly offer is visibly carried into the registration card with its billing period and price. The backend remains authoritative and this capture creates no subscription, entitlement, quota, payment, or checkout.",
        )
    finally:
        page.unroute(catalog_pattern)
        page.unroute(config_pattern)


def enforce_authority_metadata(metadata: dict[str, object]) -> None:
    authority = dict(metadata.get("authority", {}))
    unexpected_true = [name for name, value in authority.items() if name in REQUIRED_FALSE_AUTHORITY_FLAGS and value is True]
    if unexpected_true:
        raise RuntimeError(f"VQ authority metadata attempted to promote forbidden flags: {unexpected_true}")
    for flag in REQUIRED_FALSE_AUTHORITY_FLAGS:
        authority[flag] = False
    metadata["authority"] = authority


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
    enforce_authority_metadata(metadata)
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    controlled = dict(inventory.get("controlled_ui_states", {}))
    controlled["admin_marketplace"] = ["permission denied"]
    controlled["settings_subscription"] = [
        "billing restriction/grace",
        "billing restriction/suspended",
        "billing restriction/terminated",
    ]
    controlled["login"] = ["mfa challenge"]
    controlled["commercial_registration"] = ["selected commercial offer"]
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
                login_mfa_challenge(page, browser_version, counter + 4),
                registration_selected_offer(page, browser_version, counter + 5),
            ]
            for row in rows:
                append_row(row)
        finally:
            browser.close()
    update_metadata()
    print("captured 6 extended controlled UI state(s)")


if __name__ == "__main__":
    main()
