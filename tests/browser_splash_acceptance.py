from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
ARTIFACTS = ROOT / "artifacts" / "splash-browser"
HOST = "127.0.0.1"
PORT = 8765
PULSE_STATE_TIMEOUT_MS = 12000


class SplashHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        request_path = urlparse(self.path).path
        if request_path in {"/", "/splash", "/splash/"}:
            target = STATIC / "splash.html"
        elif request_path.startswith("/console/"):
            target = STATIC / request_path.removeprefix("/console/")
        else:
            self.send_response(404)
            self.end_headers()
            return

        target = target.resolve()
        if STATIC.resolve() not in target.parents and target != STATIC.resolve():
            self.send_response(403)
            self.end_headers()
            return
        if not target.is_file():
            self.send_response(404)
            self.end_headers()
            return

        payload = target.read_bytes()
        content_type, _ = mimetypes.guess_type(target.name)
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _assert_page_contract(page, *, pulse_expected: bool) -> dict[str, object]:
    page.wait_for_load_state("networkidle")
    metrics = page.evaluate(
        """() => {
          const box = (node) => {
            const r = node.getBoundingClientRect();
            return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};
          };
          return {
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            devicePixelRatio: window.devicePixelRatio,
            stage: box(document.querySelector('.stage')),
            board: (() => {
              const board = document.querySelector('#pcb-reference');
              if (!board) return null;
              return {
                complete: board.complete,
                ...box(board),
                opacity: Number.parseFloat(getComputedStyle(board).opacity),
              };
            })(),
            core: box(document.querySelector('.core')),
            execution: box(document.querySelector('.execution')),
            cardBoxes: [...document.querySelectorAll('.card')].map(card => ({
              name: card.querySelector('h3')?.textContent?.trim() || '',
              family: card.dataset.routeFamily || '',
              ...box(card),
            })),
            cards: document.querySelectorAll('.card').length,
            canonicalLayers: document.querySelectorAll('[data-canonical-route-layer]').length,
            pulseHeads: document.querySelectorAll('.pulse-head').length,
            pulseTails: document.querySelectorAll('.pulse-tail').length,
            coreTransform: getComputedStyle(document.querySelector('.core')).transform,
            firstCardTransform: getComputedStyle(document.querySelector('.card')).transform,
          };
        }"""
    )
    assert metrics["innerWidth"] == 1672
    assert metrics["innerHeight"] == 941
    assert metrics["devicePixelRatio"] == 1
    assert metrics["stage"]["x"] == 0
    assert metrics["stage"]["y"] == 0
    assert metrics["stage"]["width"] == 1672
    assert metrics["stage"]["height"] == 941
    assert metrics["board"] is not None
    assert metrics["board"]["complete"] is True
    assert metrics["board"]["x"] == 0
    assert metrics["board"]["y"] == 0
    assert metrics["board"]["width"] == 1672
    assert metrics["board"]["height"] == 941
    assert metrics["board"]["opacity"] >= 0.35
    assert metrics["core"] == {
        "x": 608,
        "y": 214,
        "width": 433,
        "height": 408,
        "right": 1041,
        "bottom": 622,
    }
    assert metrics["execution"]["x"] == 758
    assert metrics["execution"]["y"] == 665
    assert metrics["execution"]["width"] == 156
    assert metrics["execution"]["height"] == 112
    assert metrics["cards"] == 8
    assert metrics["canonicalLayers"] == 5

    card_boxes = metrics["cardBoxes"]
    assert [card["name"] for card in card_boxes] == [
        "GOVERNANCE",
        "SUPERVISION",
        "CALIBRATION",
        "ORCHESTRATION",
        "ROUTING",
        "POLICY ENGINE",
        "FEEDBACK LOOP",
        "CONTROL GATES",
    ]
    assert [card["y"] for card in card_boxes] == [87, 254, 423, 595, 87, 254, 423, 595]
    assert [card["x"] for card in card_boxes[:4]] == [80, 80, 80, 80]
    assert [card["right"] for card in card_boxes[:4]] == [415, 415, 415, 415]
    assert [card["x"] for card in card_boxes[4:]] == [1240, 1240, 1240, 1240]
    assert [card["right"] for card in card_boxes[4:]] == [1575, 1575, 1575, 1575]

    core = metrics["core"]
    for card in card_boxes:
        horizontal_overlap = min(core["right"], card["right"]) - max(core["x"], card["x"])
        vertical_overlap = min(core["bottom"], card["bottom"]) - max(core["y"], card["y"])
        assert horizontal_overlap <= 0 or vertical_overlap <= 0, f"Core overlaps card: {card['name']}"

    if pulse_expected:
        assert metrics["pulseHeads"] == 5
        assert metrics["pulseTails"] == 5
    else:
        assert metrics["pulseHeads"] == 0
        assert metrics["pulseTails"] == 0
    return metrics


def _pulse_snapshot(page) -> dict[str, object]:
    return page.evaluate(
        """() => ({
          visibleHeads: [...document.querySelectorAll('.pulse-head')]
            .filter(node => Number.parseFloat(getComputedStyle(node).opacity) > .5).length,
          visibleTails: [...document.querySelectorAll('.pulse-tail')]
            .filter(node => Number.parseFloat(getComputedStyle(node).opacity) > .3).length,
          coreSource: document.querySelector('.core').classList.contains('pulse-source'),
          receiving: [...document.querySelectorAll('.card.receiving')]
            .map(card => card.dataset.routeFamily),
        })"""
    )


def _wait_for_pulse_state(
    page,
    *,
    source: bool,
    receiver_family: str | None,
    timeout_ms: int = PULSE_STATE_TIMEOUT_MS,
) -> dict[str, object]:
    expected_receiving = [] if receiver_family is None else [receiver_family]
    page.wait_for_function(
        """({source, receiving}) => {
          const heads = [...document.querySelectorAll('.pulse-head')]
            .filter(node => Number.parseFloat(getComputedStyle(node).opacity) > .5).length;
          const tails = [...document.querySelectorAll('.pulse-tail')]
            .filter(node => Number.parseFloat(getComputedStyle(node).opacity) > .3).length;
          const coreSource = document.querySelector('.core').classList.contains('pulse-source');
          const activeReceivers = [...document.querySelectorAll('.card.receiving')]
            .map(card => card.dataset.routeFamily);
          return heads === 1 && tails === 1 && coreSource === source
            && JSON.stringify(activeReceivers) === JSON.stringify(receiving);
        }""",
        arg={"source": source, "receiving": expected_receiving},
        timeout=timeout_ms,
    )
    return _pulse_snapshot(page)


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), SplashHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    evidence: dict[str, object] = {"viewport": [1672, 941], "device_scale_factor": 1}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)

            static_context = browser.new_context(
                viewport={"width": 1672, "height": 941},
                device_scale_factor=1,
                reduced_motion="reduce",
            )
            static_page = static_context.new_page()
            static_errors: list[str] = []
            static_page.on("console", lambda msg: static_errors.append(msg.text) if msg.type == "error" else None)
            static_page.on("pageerror", lambda exc: static_errors.append(str(exc)))
            static_page.goto(f"http://{HOST}:{PORT}/", wait_until="networkidle")
            evidence["static"] = _assert_page_contract(static_page, pulse_expected=False)
            static_page.screenshot(path=str(ARTIFACTS / "splash-static-1672x941.png"), full_page=True)
            assert not static_errors, f"Static splash browser errors: {static_errors}"
            static_context.close()

            pulse_context = browser.new_context(
                viewport={"width": 1672, "height": 941},
                device_scale_factor=1,
                reduced_motion="no-preference",
            )
            pulse_page = pulse_context.new_page()
            pulse_errors: list[str] = []
            pulse_page.on("console", lambda msg: pulse_errors.append(msg.text) if msg.type == "error" else None)
            pulse_page.on("pageerror", lambda exc: pulse_errors.append(str(exc)))
            pulse_page.goto(f"http://{HOST}:{PORT}/", wait_until="networkidle")
            evidence["pulse"] = _assert_page_contract(pulse_page, pulse_expected=True)

            source_snapshot = _wait_for_pulse_state(
                pulse_page,
                source=True,
                receiver_family=None,
            )
            evidence["source_snapshot"] = source_snapshot

            receiver_snapshot = _wait_for_pulse_state(
                pulse_page,
                source=False,
                receiver_family="cyan",
            )
            evidence["receiver_snapshot"] = receiver_snapshot

            pulse_page.screenshot(path=str(ARTIFACTS / "splash-pulse-1672x941.png"), full_page=True)
            assert not pulse_errors, f"Animated splash browser errors: {pulse_errors}"
            pulse_context.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    evidence["console_errors"] = []
    (ARTIFACTS / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
