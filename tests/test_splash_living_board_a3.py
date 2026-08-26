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


def test_production_splash_keeps_dom_ui_plus_one_visible_authored_board():
    source = _source()
    required = [
        'id="pcb-reference"',
        'src="./splash_reference_board.svg"',
        'id="signal-svg"',
        'class="maestro-reference-stage"',
        "function registerSignal(",
        "function rebuildSignals()",
        "function animate(now)",
        "getTotalLength",
        "getPointAtLength",
        "requestAnimationFrame",
        ".signal-geometry{fill:none;stroke:none;pointer-events:none}",
    ]
    forbidden = [
        "function pcb(",
        "function drawSideFabric(",
        "function regionalFabric(",
        "class:'signal-base'",
        "class:'signal-wake'",
        "class:'via-node node-bloom'",
    ]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_legacy_routing_was_deleted_and_rebuilt_from_measured_visual_pins():
    board = _board()
    required = [
        'aria-label="Maestro PCB v18 measured visual-pin reconstruction"',
        'id="pcb-routing" data-topology="measured-pin-single-source"',
        'data-left-pin-x="624"',
        'data-right-pin-x="1048"',
        'data-top-pin-y="233"',
        'data-bottom-pin-y="653"',
        'id="terminal-beacons"',
        'id="passive-vias"',
        'id="module-rails"',
    ]
    forbidden = [
        "Maestro PCB v15 single-source pin fanout",
        'data-origin-x="642"',
        'data-origin-x="1030"',
        'data-origin-y="248"',
        'data-origin-y="640"',
    ]
    assert not [m for m in required if m not in board]
    assert not [m for m in forbidden if m in board]


def _route_starts(board: str) -> list[tuple[int, int]]:
    starts = []
    for d in re.findall(r'data-route="[^"]+"[^>]*d="([^"]+)"', board):
        match = re.match(r"M(\d+) (\d+)", d)
        assert match, d
        starts.append((int(match.group(1)), int(match.group(2))))
    return starts


def test_every_visible_route_origin_is_on_the_measured_core_pin_envelope():
    board = _board()
    starts = _route_starts(board)
    assert len(starts) >= 70
    allowed = []
    for x, y in starts:
        allowed.append(
            x in {624, 1048}
            or y in {233, 653}
        )
    assert all(allowed)


def test_no_route_origin_remains_on_cards_or_midfield_background():
    board = _board()
    starts = _route_starts(board)
    forbidden_x = {396, 414, 430, 438, 442, 450, 1222, 1230, 1240, 1276}
    assert not [(x, y) for x, y in starts if x in forbidden_x]


def test_side_routes_have_a_real_parallel_breakout_before_fanout():
    board = _board()
    left_ds = re.findall(r'data-route="(?:gov|sup|cal|orc)-[^"]+"[^>]*d="([^"]+)"', board)
    right_ds = re.findall(r'data-route="(?:route|pol|feed|ctrl)-[^"]+"[^>]*d="([^"]+)"', board)
    assert len(left_ds) >= 24
    assert len(right_ds) >= 24
    assert all(re.match(r"M624 \d+H575", d) for d in left_ds)
    assert all(re.match(r"M1048 \d+H1097", d) for d in right_ds)


def test_side_route_spacing_expands_toward_the_modules():
    board = _board()
    gov = re.findall(r'data-route="gov-[1-5]"[^>]*d="([^"]+)"', board)
    routing = re.findall(r'data-route="route-[1-5]"[^>]*d="([^"]+)"', board)
    assert len(gov) == 5
    assert len(routing) == 5
    # near-core starts are tightly packed by 10 px; destination Y values span a wider module band.
    gov_start_y = [int(re.match(r"M624 (\d+)", d).group(1)) for d in gov]
    gov_end_y = [int(re.search(r"V(\d+)$", d).group(1)) for d in gov]
    route_start_y = [int(re.match(r"M1048 (\d+)", d).group(1)) for d in routing]
    route_end_y = [int(re.search(r"V(\d+)$", d).group(1)) for d in routing]
    assert max(gov_end_y) - min(gov_end_y) > max(gov_start_y) - min(gov_start_y)
    assert max(route_end_y) - min(route_end_y) > max(route_start_y) - min(route_start_y)


def test_crown_and_bottom_are_pin_origin_fans_not_free_floating_paths():
    board = _board()
    crown = re.findall(r'data-route="top-[^"]+"[^>]*d="([^"]+)"', board)
    bottom = re.findall(r'data-route="bot-[^"]+"[^>]*d="([^"]+)"', board)
    assert len(crown) == 18
    assert len(bottom) == 14
    assert all(re.match(r"M\d+ 233V196", d) for d in crown)
    assert all(re.match(r"M\d+ 653V690", d) for d in bottom)


def test_dead_end_beacons_are_real_route_endpoints():
    board = _board()
    dead_ends = re.findall(r'data-terminal="dead-end"[^>]*d="([^"]+)"', board)
    assert len(dead_ends) >= 16
    endpoints = set()
    for d in dead_ends:
        nums = [int(n) for n in re.findall(r"\d+", d)]
        endpoints.add((nums[-2], nums[-1]))
    circles = {
        (int(x), int(y))
        for x, y in re.findall(r'<circle cx="(\d+)" cy="(\d+)"', board)
    }
    assert endpoints <= circles


def test_reference_board_is_dense_but_has_no_ambient_free_origin_routes():
    board = _board()
    assert board.count('data-route="') >= 70
    assert board.count("<circle") >= 40
    forbidden = [
        "M8 112",
        "M8 178",
        "M1664 126",
        "M1664 196",
        "M396 162 H",
        "M1276 162 H",
    ]
    assert not [m for m in forbidden if m in board]


def test_production_splash_is_full_landing_page_and_preserves_modules():
    source = _source()
    required = [
        'class="site-header"',
        'class="brand"',
        'class="nav"',
        "PLATFORM⌄",
        "SOLUTIONS⌄",
        "RESOURCES⌄",
        "ABOUT⌄",
        "DOCS",
        "SYSTEM STATUS",
        "ALL SYSTEMS OPERATIONAL",
        'class="signin" href="/login"',
        'class="telemetry-strip"',
        "SYSTEM METRICS",
        "THROUGHPUT",
        "LATENCY (P95)",
        "QUEUE DEPTH",
        "SYSTEM HEALTH",
        'id="governance"',
        'id="supervision"',
        'id="calibration"',
        'id="orchestration"',
        'id="routing"',
        'id="policy"',
        'id="feedback"',
        'id="control"',
        'id="execution"',
    ]
    assert not [m for m in required if m not in source]


def test_core_side_modules_and_processor_teeth_keep_visual_contract():
    source = _source()
    required = [
        "#governance{left:78px;top:91px}",
        "#routing{right:78px;top:91px}",
        "left:642px;top:248px;width:388px;height:390px",
        "transform:scale(.88)",
        "transform:scale(1.045)",
        "filter:drop-shadow(0 16px 20px rgba(0,0,0,.34))",
        "width:4px",
        "height:4px",
        "/* slim route-colored processor teeth */",
    ]
    assert not [m for m in required if m not in source]


def test_entry_gate_reduced_motion_and_cover_fit_remain_intact():
    source = _source()
    required = [
        "Enter Maestro",
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "window.location.href = '/login'",
        "@media(prefers-reduced-motion:reduce)",
        "const fit_rule='reference-cover-1672x941'",
        "Math.max(viewportWidth/1672,viewportHeight/941)",
        "--header-drop",
        "--footer-lift",
        "--telemetry-lift",
        "--safe-x",
    ]
    assert not [m for m in required if m not in source]
