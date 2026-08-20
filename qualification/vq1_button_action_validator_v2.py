from __future__ import annotations

import json
from dataclasses import asdict

import vq1_button_action_validator as base
from vq1_browser_harness import establish_qualification_session


def _ensure_session(page) -> None:
    establish_qualification_session(page)


def navigate_console(page, section: str) -> str:
    _ensure_session(page)
    page.goto(f"{base.BASE_URL}/console/", wait_until="domcontentloaded")
    selector = f'.nav-btn[data-page="{section}"]'
    button = page.locator(selector)
    try:
        button.wait_for(state="visible", timeout=5000)
    except Exception as exc:
        raise RuntimeError(
            f"Console navigation button {section!r} did not become visible; "
            f"current_url={page.url} selector={selector}"
        ) from exc
    button.click(timeout=5000)
    target = page.locator(f"#page-{section}")
    try:
        target.wait_for(state="visible", timeout=5000)
    except Exception as exc:
        raise RuntimeError(
            f"Console section {section!r} did not become visible after click; "
            f"current_url={page.url}"
        ) from exc
    return f"#page-{section}:visible"


def navigate_admin(page, section: str) -> str:
    _ensure_session(page)
    page.goto(f"{base.BASE_URL}/admin", wait_until="domcontentloaded")
    selector = f'.nav-btn[data-admin-page="{section}"]'
    button = page.locator(selector)
    try:
        button.wait_for(state="visible", timeout=5000)
    except Exception as exc:
        raise RuntimeError(
            f"Admin navigation button {section!r} did not become visible; "
            f"current_url={page.url} selector={selector}"
        ) from exc
    button.click(timeout=5000)
    page.wait_for_timeout(250)
    return ".admin-page.active"


def print_report() -> None:
    if not base.REPORT_PATH.exists():
        print(f"Button audit report was not created: {base.REPORT_PATH}")
        return
    payload = json.loads(base.REPORT_PATH.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    print("\n=== BUTTON ACTION AUDIT SUMMARY ===")
    print(f"ALL:         {totals.get('all', 0)}")
    print(f"PASS:        {totals.get('pass', 0)}")
    print(f"CONDITIONAL: {totals.get('conditional', 0)}")
    print(f"FAIL:        {totals.get('fail', 0)}")
    failures = [item for item in payload.get("results", []) if item.get("status") == "FAIL"]
    if failures:
        print("\nFailures:")
        for item in failures[:40]:
            print(
                f"- {item.get('surface')}/{item.get('section')} :: "
                f"{item.get('label') or '<unlabelled>'} :: {item.get('notes') or 'no detail'}"
            )
    print(f"\nReport: {base.REPORT_PATH}")


def write_fatal_report(exc: Exception) -> None:
    base.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "base_url": base.BASE_URL,
        "scope": "all delivered Console/Admin navigation plus all visible buttons in each active section",
        "totals": {"all": 0, "pass": 0, "conditional": 0, "fail": 1},
        "fatal_error": str(exc),
        "results": [
            asdict(
                base.ButtonResult(
                    surface="audit",
                    section="bootstrap-or-navigation",
                    index=-1,
                    label="Button action audit",
                    button_id="",
                    disabled=False,
                    status="FAIL",
                    effects=[],
                    requests=[],
                    notes=str(exc),
                )
            )
        ],
    }
    base.REPORT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    base.navigate_console = navigate_console
    base.navigate_admin = navigate_admin
    try:
        base.main()
    except Exception as exc:
        if not base.REPORT_PATH.exists():
            write_fatal_report(exc)
        print_report()
        raise
    else:
        print_report()


if __name__ == "__main__":
    main()
