from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
BOARD = STATIC / "splash_reference_board.svg"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def _board() -> str:
    return BOARD.read_text(encoding="utf-8")


def test_production_splash_keeps_dom_ui_plus_single_visible_authored_board():
    source = _source()
    required = [
        'id="pcb-reference"', 'src="./splash_reference_board.svg"', 'id="signal-svg"',
        'class="maestro-reference-stage"', "function registerSignal(", "function rebuildSignals()",
        "function animate(now)", "getTotalLength", "getPointAtLength", "requestAnimationFrame",
        ".signal-geometry{fill:none;stroke:none;pointer-events:none}",
    ]
    forbidden = [
        "function pcb(", "function drawSideFabric(", "function regionalFabric(",
        "class:'signal-base'", "class:'signal-wake'", "class:'via-node node-bloom'",
    ]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_reference_board_is_rebuilt_as_single_source_pin_fanout():
    board = _board()
    required = [
        'aria-label="Maestro PCB v15 single-source pin fanout"',
        'id="pcb-routing" data-topology="single-source"',
        'id="left-routes" data-origin-x="642"',
        'id="right-routes" data-origin-x="1030"',
        'id="crown-routes" data-origin-y="248"',
        'id="bottom-routes" data-origin-y="640"',
        'id="terminal-beacons"', 'id="passive-vias"', 'id="module-rails"',
    ]
    assert not [m for m in required if m not in board]


def test_board_has_reference_density_without_background_route_origins():
    board = _board()
    assert board.count("<path") >= 25
    assert board.count("<circle") >= 50
    assert board.count("M642 ") >= 20
    assert board.count("M1030 ") >= 20
    forbidden = ["M8 112", "M8 178", "M1664 126", "M1664 196", "M396 162 H", "M1276 162 H"]
    assert not [m for m in forbidden if m in board]


def test_side_routes_begin_aligned_and_then_diverge_progressively():
    board = _board()
    required = [
        "M642 278L612 278L570 259L520 225",
        "M642 348L612 348L570 340L520 324",
        "M1030 278L1060 278L1102 259L1152 225",
        "M1030 348L1060 348L1102 340L1152 324",
    ]
    assert not [m for m in required if m not in board]


def test_dead_end_nodes_are_attached_to_secondary_routes():
    board = _board()
    required = [
        'data-terminal="dead-end"',
        '<circle cx="450" cy="236" r="2.4" fill="#36bfff"/>',
        '<circle cx="448" cy="338" r="2.4" fill="#23d8c8"/>',
        '<circle cx="1222" cy="238" r="2.4" fill="#e59a20"/>',
        '<circle cx="1226" cy="432" r="2.4" fill="#23d8c8"/>',
    ]
    assert not [m for m in required if m not in board]


def test_crown_and_bottom_start_only_at_processor_edges():
    board = _board()
    top_starts = re.findall(r"M(\d+) 248", board)
    bottom_starts = re.findall(r"M(\d+) 640", board)
    assert len(top_starts) >= 15
    assert len(bottom_starts) >= 12
    assert all(642 <= int(x) <= 1030 for x in top_starts)
    assert all(642 <= int(x) <= 1030 for x in bottom_starts)


def test_production_splash_is_full_landing_page_and_preserves_modules():
    source = _source()
    required = [
        'class="site-header"', 'class="brand"', 'class="nav"', "PLATFORM⌄", "SOLUTIONS⌄",
        "RESOURCES⌄", "ABOUT⌄", "DOCS", "SYSTEM STATUS", "ALL SYSTEMS OPERATIONAL",
        'class="signin" href="/login"', 'class="telemetry-strip"', "SYSTEM METRICS",
        "THROUGHPUT", "LATENCY (P95)", "QUEUE DEPTH", "SYSTEM HEALTH",
        'id="governance"', 'id="supervision"', 'id="calibration"', 'id="orchestration"',
        'id="routing"', 'id="policy"', 'id="feedback"', 'id="control"', 'id="execution"',
    ]
    assert not [m for m in required if m not in source]


def test_core_side_modules_and_processor_teeth_keep_visual_contract():
    source = _source()
    required = [
        "#governance{left:78px;top:91px}", "#routing{right:78px;top:91px}",
        "left:642px;top:248px;width:388px;height:390px", "transform:scale(.88)",
        "transform:scale(1.045)", "filter:drop-shadow(0 16px 20px rgba(0,0,0,.34))",
        "width:4px", "height:4px", "/* slim route-colored processor teeth */",
    ]
    assert not [m for m in required if m not in source]


def test_entry_gate_reduced_motion_and_cover_fit_remain_intact():
    source = _source()
    required = [
        "Enter Maestro", "maestro_descent_gate_seen", "maestro_descent_gate_seen_at",
        "window.location.href = '/login'", "@media(prefers-reduced-motion:reduce)",
        "const fit_rule='reference-cover-1672x941'", "Math.max(viewportWidth/1672,viewportHeight/941)",
        "--header-drop", "--footer-lift", "--telemetry-lift", "--safe-x",
    ]
    assert not [m for m in required if m not in source]
