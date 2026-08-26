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


def _routes(board: str) -> list[str]:
    return re.findall(r'data-route="[^"]+"[^>]*d="([^"]+)"', board)


def _start(d: str) -> tuple[int, int]:
    m = re.match(r"M(\d+) (\d+)", d)
    assert m, d
    return int(m.group(1)), int(m.group(2))


def test_contract_targets_measured_visual_pin_geometry():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v18"
    assert contract["minimum_score"] >= 99
    assert contract["architecture"]["visible_route_sources"] == 1
    assert contract["architecture"]["legacy_board_must_be_deleted_before_rebuild"] is True
    assert contract["architecture"]["pulse_overlay_must_not_draw_routes"] is True
    assert contract["logical_layout"]["core_visual_pin_envelope"] == {
        "left_x": 624,
        "right_x": 1048,
        "top_y": 233,
        "bottom_y": 653,
        "tolerance_px": 3,
    }


def test_board_is_v18_post_delete_reconstruction():
    board = _board()
    assert 'Maestro PCB v18 measured visual-pin reconstruction' in board
    assert 'data-topology="measured-pin-single-source"' in board
    assert 'data-left-pin-x="624"' in board
    assert 'data-right-pin-x="1048"' in board
    assert 'data-top-pin-y="233"' in board
    assert 'data-bottom-pin-y="653"' in board
    assert 'Maestro PCB v15 single-source pin fanout' not in board


def test_every_visible_route_starts_at_the_measured_pin_envelope():
    board = _board()
    pcb = _contract()["pcb"]
    routes = _routes(board)
    assert len(routes) >= pcb["route_subpaths_min"]
    for d in routes:
        x, y = _start(d)
        assert x in {624, 1048} or y in {233, 653}, d


def test_side_routes_are_parallel_at_origin_then_fan_out():
    board = _board()
    left = re.findall(r'data-route="(?:gov|sup|cal|orc)-[^"]+"[^>]*d="([^"]+)"', board)
    right = re.findall(r'data-route="(?:route|pol|feed|ctrl)-[^"]+"[^>]*d="([^"]+)"', board)
    assert left and right
    assert all(re.match(r"M624 \d+H575", d) for d in left)
    assert all(re.match(r"M1048 \d+H1097", d) for d in right)


def test_top_and_bottom_routes_start_on_visual_teeth():
    board = _board()
    crown = re.findall(r'data-route="top-[^"]+"[^>]*d="([^"]+)"', board)
    bottom = re.findall(r'data-route="bot-[^"]+"[^>]*d="([^"]+)"', board)
    assert len(crown) == 18
    assert len(bottom) == 14
    assert all(re.match(r"M\d+ 233V196", d) for d in crown)
    assert all(re.match(r"M\d+ 653V690", d) for d in bottom)


def test_dead_end_nodes_are_actual_route_endpoints():
    board = _board()
    dead = re.findall(r'data-terminal="dead-end"[^>]*d="([^"]+)"', board)
    assert len(dead) >= 16
    endpoints = set()
    for d in dead:
        nums = [int(n) for n in re.findall(r"\d+", d)]
        endpoints.add((nums[-2], nums[-1]))
    nodes = {(int(x), int(y)) for x, y in re.findall(r'<circle cx="(\d+)" cy="(\d+)"', board)}
    assert endpoints <= nodes


def test_no_legacy_free_origin_fabric_remains():
    board = _board()
    for marker in ["M8 112", "M8 178", "M1664 126", "M1664 196", 'data-origin-x="642"', 'data-origin-x="1030"']:
        assert marker not in board


def test_motion_overlay_is_pulse_only():
    source = _source()
    assert 'id="signal-svg"' in source
    assert '.signal-geometry{fill:none;stroke:none;pointer-events:none}' in source
    assert "class:'signal-geometry'" in source
    assert "class:'signal-base'" not in source
    assert "class:'signal-wake'" not in source


def test_identity_core_entry_and_viewport_contracts_remain_intact():
    source = _source()
    required = [
        'class="maestro-emblem"',
        'class="brand-word">MAESTRO<b>.</b>',
        'class="core-emblem"',
        "Govern • Supervise • Calibrate • Orchestrate",
        "Enter Maestro",
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "window.location.href = '/login'",
        "transform:scale(1.045)",
        "transform:scale(.88)",
        "width:4px",
        "height:4px",
        "const fit_rule='reference-cover-1672x941'",
        "Math.max(viewportWidth/1672,viewportHeight/941)",
        "@media(prefers-reduced-motion:reduce)",
    ]
    assert not [m for m in required if m not in source]
    assert re.search(r"[\u0600-\u06FF]", source) is None
