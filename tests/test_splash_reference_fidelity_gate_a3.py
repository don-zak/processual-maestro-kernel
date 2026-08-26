import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
BOARD = STATIC / "splash_reference_board.svg"
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_fidelity_contract_a3.json"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def _board() -> str:
    return BOARD.read_text(encoding="utf-8")


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _route_ds(board: str) -> list[str]:
    routing = board.split('id="pcb-routing"', 1)[1].split('</g><g class="t"', 1)[0]
    return re.findall(r'<path[^>]*\bclass="r [^"]+"[^>]*\bd="([^"]+)"', routing)


def _subpaths(d: str) -> list[str]:
    return [part.strip() for part in re.split(r'(?=M\d)', d) if part.strip()]


def _start_xy(subpath: str) -> tuple[int, int]:
    match = re.match(r'M(\d+)\s+(\d+)', subpath)
    assert match, subpath
    return int(match.group(1)), int(match.group(2))


def test_contract_is_rendered_geometry_focused():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v17"
    assert contract["minimum_score"] >= 99
    assert sum(contract["scoring"].values()) == 100
    assert contract["architecture"]["mode"] == "single-visible-svg-plus-pulse-overlay"
    assert contract["architecture"]["visible_route_sources"] == 1
    assert contract["architecture"]["pulse_overlay_must_not_draw_routes"] is True


def test_reference_stage_and_layout_are_locked():
    contract = _contract()
    assert contract["reference_stage"] == {
        "width": 1672,
        "height": 941,
        "aspect_ratio": "1672:941",
        "fit_rule": "reference-cover-1672x941",
    }
    layout = contract["logical_layout"]
    assert layout["core_bounds"] == {"x": 642, "y": 248, "w": 388, "h": 390, "tolerance_px": 18}
    assert layout["side_module_visual_scale"] == 0.88
    assert layout["core_visual_scale"] == 1.045


def test_board_has_one_visible_route_topology_and_required_palette():
    board = _board()
    pcb = _contract()["pcb"]
    assert 'data-topology="single-source"' in board
    assert board.count('id="pcb-routing"') == 1
    assert board.count("<path") >= pcb["authored_paths_min"]
    assert board.count("<circle") >= pcb["authored_nodes_min"]
    for color in ["#36bfff", "#e59a20", "#23d8c8", "#a7d67b", "#c16fff"]:
        assert f'stroke="{color}"' in board or f'fill="{color}"' in board


def test_every_visible_route_subpath_starts_on_a_processor_edge():
    board = _board()
    contract = _contract()["pcb"]
    left_x = contract["left_origin_x"]
    right_x = contract["right_origin_x"]
    top_y = contract["top_origin_y"]
    bottom_y = contract["bottom_origin_y"]

    subpaths = [sub for d in _route_ds(board) for sub in _subpaths(d)]
    assert len(subpaths) >= contract["route_subpaths_min"]

    for sub in subpaths:
        x, y = _start_xy(sub)
        assert x in {left_x, right_x} or y in {top_y, bottom_y}, sub


def test_side_routes_have_an_aligned_stem_before_fanout():
    board = _board()
    minimum = _contract()["pcb"]["aligned_stem_min_px"]
    side_subpaths = []
    for d in _route_ds(board):
        for sub in _subpaths(d):
            x, y = _start_xy(sub)
            if x in {642, 1030}:
                side_subpaths.append(sub)

    assert side_subpaths
    for sub in side_subpaths:
        numbers = [int(n) for n in re.findall(r'\d+', sub)]
        x0, y0, x1, y1 = numbers[:4]
        assert y1 == y0, sub
        assert abs(x1 - x0) >= minimum, sub


def test_fanout_spacing_grows_away_from_core():
    board = _board()
    # Representative primary routes: near-core vertical displacement is zero/small,
    # while outer segments intentionally diverge toward their destination bands.
    left = re.search(r'd="(M642 278[^\"]+)" stroke="#36bfff"', board)
    right = re.search(r'd="(M1030 278[^\"]+)" stroke="#e59a20"', board)
    assert left and right
    for route in (left.group(1), right.group(1)):
        first = _subpaths(route)[0]
        points = [(int(x), int(y)) for x, y in re.findall(r'(\d+)\s+(\d+)', first)]
        start_y = points[0][1]
        assert points[1][1] == start_y
        assert abs(points[-1][1] - start_y) > abs(points[2][1] - start_y)


def test_dead_ends_are_true_route_endpoints_with_terminal_beacons():
    board = _board()
    assert 'data-terminal="dead-end"' in board
    assert 'id="terminal-beacons"' in board
    assert board.count('r="2.4"') >= 12
    assert board.count('r="2.5"') >= 20


def test_motion_overlay_is_pulse_only_and_does_not_draw_a_second_visible_fabric():
    source = _source()
    required = [
        'id="signal-svg"', '.signal-geometry{fill:none;stroke:none;pointer-events:none}',
        "class:'signal-geometry'", "getTotalLength", "getPointAtLength", "requestAnimationFrame(animate)",
    ]
    forbidden = ["class:'signal-base'", "class:'signal-wake'", "class:'via-node node-bloom'"]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_identity_core_entry_and_viewport_contracts_remain_intact():
    source = _source()
    required = [
        'class="maestro-emblem"', 'class="brand-word">MAESTRO<b>.</b>', 'class="core-emblem"',
        "Govern • Supervise • Calibrate • Orchestrate", "Enter Maestro",
        "maestro_descent_gate_seen", "maestro_descent_gate_seen_at", "window.location.href = '/login'",
        "transform:scale(1.045)", "transform:scale(.88)", "width:4px", "height:4px",
        "const fit_rule='reference-cover-1672x941'", "Math.max(viewportWidth/1672,viewportHeight/941)",
        "@media(prefers-reduced-motion:reduce)",
    ]
    assert not [m for m in required if m not in source]
    assert re.search(r"[\u0600-\u06FF]", source) is None
