import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
BLUEPRINT = STATIC / "splash_reference_blueprint.js"
MODEL = STATIC / "splash_routing_model.js"
ROUTING = STATIC / "splash_routing.js"
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_fidelity_contract_a3.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_targets_v21_reference_blueprint_fabric():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v21"
    assert contract["minimum_score"] >= 99
    assert contract["reference_stage"]["source"] == "pivot-reference-image"
    assert contract["architecture"]["mode"] == "inline-generated-reference-blueprint-routing"
    assert contract["architecture"]["visible_route_sources"] == 1
    assert contract["architecture"]["reference_blueprint_required"] is True
    assert contract["architecture"]["legacy_external_board_forbidden"] is True
    assert contract["architecture"]["legacy_authored_signal_map_forbidden"] is True
    assert contract["architecture"]["pulse_must_follow_visible_routes"] is True
    assert contract["pcb"]["pin_count_expected"] == 120
    assert contract["pcb"]["destination_route_ratio_max"] <= 0.16
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


def test_reference_blueprint_is_explicit_and_drives_model():
    blueprint = _read(BLUEPRINT)
    model = _read(MODEL)
    assert "A3-splash-reference-blueprint-v21" in blueprint
    assert "source: 'pivot-reference-image'" in blueprint
    assert "import { REFERENCE_BLUEPRINT, corridorFor }" in model
    assert "version: REFERENCE_BLUEPRINT.version" in model
    for marker in ["left: 624", "right: 1048", "top: 233", "bottom: 653"]:
        assert marker in model
    assert "pinCount: 120" in model


def test_destination_routes_are_a_small_minority_of_reference_fabric():
    blueprint = _read(BLUEPRINT)
    model = _read(MODEL)
    assert "destinationRatioMax: 0.16" in blueprint
    assert "destinationRatioMax: REFERENCE_BLUEPRINT.destinationRatioMax" in model
    assert "modulePins" in blueprint
    assert "bottom: Object.freeze([14, 15])" in blueprint


def test_only_two_route_widths_exist():
    blueprint = _read(BLUEPRINT)
    routing = _read(ROUTING)
    assert "routeWeights: Object.freeze({ thick: 1.08, thin: 0.66 })" in blueprint
    assert "ROUTE_WEIGHTS[pin.weight]" in routing
    assert "ROUTE_WEIGHTS.thin" in routing
    assert "micro" not in blueprint + routing


def test_aligned_breakout_then_corridor_spread_is_encoded_in_generator():
    routing = _read(ROUTING)
    required = [
        "const points = [[pin.x, pin.y], [stemX, pin.y]]",
        "const points = [[pin.x, pin.y], [pin.x, stemY]]",
        "function corridorY(pin)",
        "const x1 = stemX + dir * Math.max(22, Math.round(reach * 0.22))",
        "const x2 = stemX + dir * Math.max(48, Math.round(reach * 0.48))",
        "const x3 = stemX + dir * Math.max(70, Math.round(reach * 0.74))",
        "const y1 = lerp(pin.y, cy, 0.22)",
        "const y2 = lerp(pin.y, cy, 0.54)",
        "const y3 = lerp(pin.y, cy, 0.82)",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_five_route_variants_prevent_uniform_bus_copying():
    routing = _read(ROUTING)
    for variant in range(5):
        assert f"if (pin.variant === {variant})" in routing
    model = _read(MODEL)
    assert "variant: (i * 7" in model
    assert "variant: (i * 9" in model


def test_reference_specific_reach_bands_and_true_terminal_network_are_present():
    blueprint = _read(BLUEPRINT)
    routing = _read(ROUTING)
    for marker in [
        "sideReach: Object.freeze({ short: [58, 86], medium: [98, 136], long: [146, 188] })",
        "topReach: Object.freeze({ short: [42, 66], medium: [76, 108], long: [118, 164] })",
        "bottomReach: Object.freeze({ short: [38, 58], medium: [64, 92], long: [98, 132] })",
    ]:
        assert marker in blueprint
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
