from __future__ import annotations

import threading

from playwright.sync_api import sync_playwright

from browser_splash_acceptance import HOST, PORT, SplashHandler
from http.server import ThreadingHTTPServer


EXPECTED_TAB_TARGETS = [
    {"text": "MAESTRO.", "href": "/"},
    {"text": "PLATFORM⌄", "href": "#platform"},
    {"text": "SOLUTIONS⌄", "href": "#solutions"},
    {"text": "RESOURCES⌄", "href": "#resources"},
    {"text": "DOCS", "href": "/docs"},
    {"text": "SIGN IN", "href": "/login"},
    {"text": "ENTER MAESTRO →", "href": "/login"},
]


def _active_target(page) -> dict[str, object]:
    return page.evaluate(
        """() => {
          const node = document.activeElement;
          const style = getComputedStyle(node);
          return {
            tag: node?.tagName || '',
            text: node?.textContent?.trim().replace(/\s+/g, ' ') || '',
            href: node?.getAttribute?.('href') || '',
            outlineStyle: style.outlineStyle,
            outlineWidth: style.outlineWidth,
            outlineColor: style.outlineColor,
          };
        }"""
    )


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT + 1), SplashHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1672, "height": 941},
                device_scale_factor=1,
                reduced_motion="reduce",
            )
            page = context.new_page()
            errors: list[str] = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(f"http://{HOST}:{PORT + 1}/", wait_until="networkidle")

            observed: list[dict[str, object]] = []
            for expected in EXPECTED_TAB_TARGETS:
                page.keyboard.press("Tab")
                target = _active_target(page)
                observed.append(target)
                assert target["tag"] == "A", target
                assert target["text"] == expected["text"], (target, expected)
                assert target["href"] == expected["href"], (target, expected)
                assert target["outlineStyle"] != "none", target
                assert target["outlineWidth"] != "0px", target

            assert not errors, f"Splash keyboard browser errors: {errors}"
            print({"keyboard_targets": observed, "console_errors": errors})
            context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
