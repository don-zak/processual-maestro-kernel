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


def _route_elements(board: str) -> list[tuple[str, str]]:
    return re.findall(r'<path class="route [^"]+"([^>]*) d="([^"]+)"', board)


def _subpaths(d: str) -> list[str]:
    return ["M" + chunk for chunk in d.split("M")[1:]]


def _start(d: str) -> tuple[int, int]:
    m = re.match(r"M(\d+) (\d+)", d)
    assert m, d
    return int(m.group(1)), int(m.group(2))


def _end(d: str) -> tuple[int, int]:
    nums = [int(n) for n in re.findall(r"\d+", d)]
    assert len(nums) >= 2, d
    return nums[-2], nums[-1]


def test_production_splash_keeps_one_visible_board_and_pulse_only_overlay():
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
        ".signal-geometry{fill:none;stroke:none;pointer-events:none}",
    ]
    forbidden = ["class:'signal-base'", "class:'signal-wake'", "function drawSideFabric("]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_v19_staged_tooth_fabric_replaces_uniform_bus_topology():
    board = _board()
    required = [
        'aria-label="Maestro PCB v19 staged tooth-fabric reconstruction"',
        'data-topology="staged-tooth-fabric"',
        'data-route-weights="2"',
        'data-destination-minority="true"',
        'data-left-pin-x="624"',
        'data-right-pin-x="1048"',
        'data-top-pin-y="233"',
        'data-bottom-pin-y="653"',
        'id="terminal-beacons"',
        'id="passive-vias"',
    ]
    assert not [m for m in required if m not in board]
    assert "Maestro PCB v18 measured visual-pin reconstruction" not in board


def test_all_visible_route_subpaths_originate_on_core_teeth():
    board = _board()
    subpaths = [sub for _, d in _route_elements(board) for sub in _subpaths(d)]
    assert len(subpaths) >= 120
    for d in subpaths:
        x, y = _start(d)
        assert x in {624, 1048} or y in {233, 653}, d


def test_side_routes_begin_with_aligned_breakout_before_spreading():
    board = _board()
    subs = [sub for _, d in _route_elements(board) for sub in _subpaths(d)]
    left = [d for d in subs if d.startswith("M624 ")]
    right = [d for d in subs if d.startswith("M1048 ")]
    assert len(left) >= 25 and len(right) >= 25
    assert all(re.match(r"M624 \d+H575", d) for d in left)
    assert all(re.match(r"M1048 \d+H1097", d) for d in right)


def test_destination_routes_are_the_minority_and_field_routes_dominate():
    board = _board()
    destination = 0
    field = 0
    for attrs, d in _route_elements(board):
        count = len(_subpaths(d))
        if 'data-destination="module"' in attrs:
            destination += count
        else:
            field += count
    total = destination + field
    assert total >= 120
    assert destination > 0
    assert destination / total < 0.25
    assert field > destination * 3


def test_exactly_two_route_weight_classes_are_used():
    board = _board()
    weights = set(re.findall(r'data-weight="([^"]+)"', board))
    assert weights == {"thick", "thin"}
    assert ".thick{stroke-width:1.15" in board
    assert ".thin{stroke-width:.68" in board
    assert "primary" not in board and "secondary" not in board and "micro" not in board


def test_field_routes_have_short_medium_and_long_reach_bands():
    board = _board()
    reaches = []
    for attrs, d in _route_elements(board):
        if 'data-destination="field"' not in attrs:
            continue
        for sub in _subpaths(d):
            sx, sy = _start(sub)
            ex, ey = _end(sub)
            reaches.append(abs(ex - sx) + abs(ey - sy))
    assert any(r < 130 for r in reaches)
    assert any(130 <= r < 230 for r in reaches)
    assert any(r >= 230 for r in reaches)


def test_top_and_bottom_teeth_are_active_fabrics_not_single_execution_buses():
    board = _board()
    subs = [sub for _, d in _route_elements(board) for sub in _subpaths(d)]
    top = [d for d in subs if re.match(r"M\d+ 233", d)]
    bottom = [d for d in subs if re.match(r"M\d+ 653", d)]
    assert len(top) >= 28
    assert len(bottom) >= 28
    assert all("V196" in d for d in top)
    assert all("V690" in d for d in bottom)


def test_terminal_beacons_are_attached_to_many_field_endpoints():
    board = _board()
    circles = {(int(x), int(y)) for x, y in re.findall(r'<circle cx="(\d+)" cy="(\d+)"', board)}
    field_endpoints = []
    for attrs, d in _route_elements(board):
        if 'data-destination="field"' in attrs:
            field_endpoints.extend(_end(sub) for sub in _subpaths(d))
    attached = [p for p in field_endpoints if p in circles]
    assert len(attached) >= 30


def test_color_families_and_side_module_integration_remain_present():
    board = _board()
    for marker in ["#36bfff", "#23d8c8", "#a7d67b", "#f5a623", "#c16fff", 'id="module-rails"']:
        assert marker in board


def test_production_splash_preserves_layout_core_and_entry_contract():
    source = _source()
    required = [
        "#governance{left:78px;top:91px}",
        "#routing{right:78px;top:91px}",
        "left:642px;top:248px;width:388px;height:390px",
        "transform:scale(.88)",
        "transform:scale(1.045)",
        "/* slim route-colored processor teeth */",
        "Enter Maestro",
        "maestro_descent_gate_seen",
        "window.location.href = '/login'",
        "@media(prefers-reduced-motion:reduce)",
        "const fit_rule='reference-cover-1672x941'",
    ]
    assert not [m for m in required if m not in source]
