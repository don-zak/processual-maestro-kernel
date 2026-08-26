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


def _elements(board: str) -> list[tuple[str, str]]:
    return re.findall(r'<path class="route [^"]+"([^>]*) d="([^"]+)"', board)


def _subs(d: str) -> list[str]:
    return ["M" + chunk for chunk in d.split("M")[1:]]


def _start(d: str) -> tuple[int, int]:
    m = re.match(r"M(\d+) (\d+)", d)
    assert m, d
    return int(m.group(1)), int(m.group(2))


def test_contract_targets_v19_staged_tooth_fabric():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v19"
    assert contract["minimum_score"] >= 99
    assert contract["architecture"]["visible_route_sources"] == 1
    assert contract["architecture"]["pulse_overlay_must_not_draw_routes"] is True
    assert contract["pcb"]["topology"] == "staged-tooth-fabric"
    assert contract["pcb"]["destination_route_ratio_max"] <= 0.25
    assert contract["pcb"]["route_weight_classes_exact"] == 2


def test_board_is_v19_and_preserves_measured_pin_envelope():
    board = _board()
    assert 'Maestro PCB v19 staged tooth-fabric reconstruction' in board
    assert 'data-topology="staged-tooth-fabric"' in board
    assert 'data-route-weights="2"' in board
    assert 'data-destination-minority="true"' in board
    for marker in ['data-left-pin-x="624"', 'data-right-pin-x="1048"', 'data-top-pin-y="233"', 'data-bottom-pin-y="653"']:
        assert marker in board


def test_every_route_subpath_starts_on_the_visual_pin_envelope():
    board = _board()
    subs = [sub for _, d in _elements(board) for sub in _subs(d)]
    assert len(subs) >= _contract()["pcb"]["route_subpaths_min"]
    for d in subs:
        x, y = _start(d)
        assert x in {624, 1048} or y in {233, 653}, d


def test_destination_routes_are_a_small_minority_of_total_tooth_fabric():
    destination = total = 0
    for attrs, d in _elements(_board()):
        count = len(_subs(d))
        total += count
        if 'data-destination="module"' in attrs:
            destination += count
    assert destination > 0
    assert destination / total < _contract()["pcb"]["destination_route_ratio_max"]


def test_only_two_route_widths_exist():
    board = _board()
    weights = set(re.findall(r'data-weight="([^"]+)"', board))
    assert weights == set(_contract()["pcb"]["allowed_route_weights"])
    assert 'stroke-width:1.15' in board
    assert 'stroke-width:.68' in board
    assert 'stroke-width:.48' not in board


def test_side_breakout_is_aligned_before_progressive_spread():
    subs = [sub for _, d in _elements(_board()) for sub in _subs(d)]
    left = [d for d in subs if d.startswith("M624 ")]
    right = [d for d in subs if d.startswith("M1048 ")]
    assert left and right
    assert all(re.match(r"M624 \d+H575", d) for d in left)
    assert all(re.match(r"M1048 \d+H1097", d) for d in right)
    assert any("L430" in d or "L422" in d for d in left)
    assert any("L1242" in d or "L1250" in d for d in right)


def test_top_bottom_and_field_termination_network_are_present():
    board = _board()
    subs = [sub for _, d in _elements(board) for sub in _subs(d)]
    assert len([d for d in subs if re.match(r"M\d+ 233", d)]) >= 28
    assert len([d for d in subs if re.match(r"M\d+ 653", d)]) >= 28
    assert 'id="terminal-beacons"' in board
    assert board.count("<circle") >= 40


def test_motion_overlay_remains_pulse_only_and_identity_is_preserved():
    source = _source()
    assert 'id="signal-svg"' in source
    assert '.signal-geometry{fill:none;stroke:none;pointer-events:none}' in source
    assert "class:'signal-base'" not in source
    assert "class:'signal-wake'" not in source
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
        "const fit_rule='reference-cover-1672x941'",
        "@media(prefers-reduced-motion:reduce)",
    ]
    assert not [m for m in required if m not in source]
    assert re.search(r"[\u0600-\u06FF]", source) is None
