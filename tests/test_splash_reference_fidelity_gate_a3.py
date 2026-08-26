import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
MODEL = STATIC / "splash_routing_model.js"
ROUTING = STATIC / "splash_routing.js"
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_fidelity_contract_a3.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_targets_v20_generated_pin_fabric():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v20"
    assert contract["minimum_score"] >= 99
    assert contract["architecture"]["mode"] == "inline-generated-single-source-routing"
    assert contract["architecture"]["visible_route_sources"] == 1
    assert contract["architecture"]["legacy_external_board_forbidden"] is True
    assert contract["architecture"]["legacy_authored_signal_map_forbidden"] is True
    assert contract["architecture"]["pulse_must_follow_visible_routes"] is True
    assert contract["pcb"]["destination_route_ratio_max"] <= 0.20
    assert contract["pcb"]["route_weight_classes_exact"] == 2


def test_splash_contains_inline_generated_board_and_no_legacy_geometry():
    source = _read(SPLASH)
    assert 'id="pcb-board"' in source
    assert 'id="pcb-routes"' in source
    assert 'id="pcb-branches"' in source
    assert 'id="pcb-terminals"' in source
    assert 'id="pcb-pulses"' in source
    assert 'src="./splash_routing.js"' in source
    assert 'id="pcb-reference"' not in source
    assert "splash_reference_board.svg" not in source
    assert "authoredSignalMap" not in source


def test_model_preserves_measured_visual_pin_envelope():
    model = _read(MODEL)
    for marker in ["left: 624", "right: 1048", "top: 233", "bottom: 653"]:
        assert marker in model
    assert "const SIDE_Y = Array.from({ length: 28 }" in model
    assert "const EDGE_X = Array.from({ length: 30 }" in model


def test_destination_routes_are_a_small_minority_of_generated_fabric():
    model = _read(MODEL)
    assert "destinationRatioMax: 0.20" in model
    assert model.count("indexes: [") == 8
    assert "[13, 14, 15].includes(i)" in model


def test_only_two_route_widths_exist():
    model = _read(MODEL)
    routing = _read(ROUTING)
    assert "ROUTE_WEIGHTS = Object.freeze({ thick: 1.1, thin: 0.68 })" in model
    assert "ROUTE_WEIGHTS[pin.weight]" in routing
    assert "ROUTE_WEIGHTS.thin" in routing
    assert "micro" not in model + routing


def test_aligned_breakout_then_progressive_spread_is_encoded_in_generator():
    routing = _read(ROUTING)
    required = [
        "const points = [[pin.x, pin.y], [stemX, pin.y]]",
        "const points = [[pin.x, pin.y], [pin.x, stemY]]",
        "const x1 = stemX + dir * Math.round(reach * 0.26)",
        "const x2 = stemX + dir * Math.round(reach * 0.56)",
        "const x3 = stemX + dir * Math.round(reach * 0.82)",
        "const y1 = stemY + dir * Math.round(reach * 0.27)",
        "const y2 = stemY + dir * Math.round(reach * 0.58)",
        "const y3 = stemY + dir * Math.round(reach * 0.84)",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_five_route_variants_prevent_uniform_bus_copying():
    routing = _read(ROUTING)
    for variant in range(5):
        assert f"if (pin.variant === {variant})" in routing
    assert "variant: (i * 7" in _read(MODEL)
    assert "variant: (i * 9" in _read(MODEL)


def test_short_medium_long_and_true_terminal_network_are_present():
    model = _read(MODEL)
    routing = _read(ROUTING)
    for marker in ["short: [82, 126]", "medium: [146, 218]", "long: [236, 322]"]:
        assert marker in model
    assert "const [x, y] = points[points.length - 1]" in routing
    assert "class: 'pcb-terminal'" in routing


def test_motion_uses_visible_route_geometry_and_identity_is_preserved():
    source = _read(SPLASH)
    routing = _read(ROUTING)
    required = [
        "pulseRoutes.push({ pin, route, color })",
        "item.route.getTotalLength()",
        "item.route.getPointAtLength",
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
    combined = source + routing
    assert not [marker for marker in required if marker not in combined]
    assert "authoredSignalMap" not in combined
    assert re.search(r"[\u0600-\u06FF]", source) is None
