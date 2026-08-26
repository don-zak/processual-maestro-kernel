from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
BLUEPRINT = STATIC / "splash_reference_blueprint.js"
MODEL = STATIC / "splash_routing_model.js"
ROUTING = STATIC / "splash_routing.js"
LEGACY = STATIC / "splash_reference_board.svg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_legacy_authored_board_is_deleted_and_inline_board_is_canonical():
    source = _read(SPLASH)
    assert not LEGACY.exists()
    assert 'id="pcb-reference"' not in source
    assert "splash_reference_board.svg" not in source
    assert "authoredSignalMap" not in source
    assert 'id="pcb-board"' in source
    assert 'id="pcb-routes"' in source
    assert 'id="pcb-branches"' in source
    assert 'id="pcb-terminals"' in source
    assert 'id="pcb-pulses"' in source
    assert 'type="module" src="./splash_routing.js"' in source


def test_model_represents_all_four_core_edges_as_active_pin_families():
    model = _read(MODEL)
    assert "pinCount: 120" in model
    assert "const SIDE_Y = Array.from({ length: 30 }" in model
    assert "const EDGE_X = Array.from({ length: 30 }" in model
    assert "for (const side of ['left', 'right'])" in model
    assert "for (const side of ['top', 'bottom'])" in model
    assert "export const PINS = Object.freeze(buildPins())" in model


def test_reference_blueprint_makes_module_reach_a_small_minority():
    blueprint = _read(BLUEPRINT)
    model = _read(MODEL)
    assert "destinationRatioMax: 0.16" in blueprint
    assert "modulePins" in blueprint
    assert "destinationRatioMax: REFERENCE_BLUEPRINT.destinationRatioMax" in model
    assert "destination.type === 'field'" in model


def test_exactly_two_route_weight_classes_are_defined_and_rendered():
    blueprint = _read(BLUEPRINT)
    routing = _read(ROUTING)
    assert "routeWeights: Object.freeze({ thick: 1.08, thin: 0.66 })" in blueprint
    assert "ROUTE_WEIGHTS[pin.weight]" in routing
    assert "ROUTE_WEIGHTS.thin" in routing
    assert "micro" not in blueprint + routing


def test_side_routes_have_parallel_breakout_before_reference_corridor_spread():
    routing = _read(ROUTING)
    required = [
        "const stemX = pin.x + dir * CONTRACT.sideStem",
        "const points = [[pin.x, pin.y], [stemX, pin.y]]",
        "function corridorY(pin)",
        "const x1 = stemX + dir * Math.max(22, Math.round(reach * 0.22))",
        "const x2 = stemX + dir * Math.max(48, Math.round(reach * 0.48))",
        "const x3 = stemX + dir * Math.max(70, Math.round(reach * 0.74))",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_top_and_bottom_routes_break_vertical_forest_after_stem():
    routing = _read(ROUTING)
    required = [
        "const stemY = pin.y + dir * CONTRACT.verticalStem",
        "const points = [[pin.x, pin.y], [pin.x, stemY]]",
        "const centerBias = (pin.x - CORE.centerX) / 212",
        "const x1 = pin.x + outward * (baseSpread * 0.35)",
        "const x2 = pin.x + outward * (baseSpread + variantSpread * 0.35)",
        "const x3 = pin.x + outward * (baseSpread + variantSpread)",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_field_routes_have_reference_specific_short_medium_long_bands():
    blueprint = _read(BLUEPRINT)
    for marker in [
        "sideReach: Object.freeze({ short: [58, 86], medium: [98, 136], long: [146, 188] })",
        "topReach: Object.freeze({ short: [42, 66], medium: [76, 108], long: [118, 164] })",
        "bottomReach: Object.freeze({ short: [38, 58], medium: [64, 92], long: [98, 132] })",
    ]:
        assert marker in blueprint


def test_branches_are_controlled_and_begin_on_parent_geometry():
    routing = _read(ROUTING)
    assert "function buildBranch(pin, mainPoints)" in routing
    assert "const origin = mainPoints[originIndex]" in routing
    assert "'data-branch-parent': pin.id" in routing
    assert "if (!pin.branch" in routing


def test_terminal_beacons_are_bound_to_real_route_endpoints():
    routing = _read(ROUTING)
    assert "const [x, y] = points[points.length - 1]" in routing
    assert "terminalsLayer.append(terminal(points, color))" in routing
    assert "terminalsLayer.append(terminal(branchPoints, color, true))" in routing


def test_pulses_follow_selected_visible_routes_instead_of_duplicate_geometry():
    source = _read(SPLASH)
    routing = _read(ROUTING)
    blueprint = _read(BLUEPRINT)
    assert "pulseRatioMax: 0.18" in blueprint
    assert "pulseRoutes.push({ pin, route, color })" in routing
    assert "item.route.getTotalLength()" in routing
    assert "item.route.getPointAtLength" in routing
    assert "authoredSignalMap" not in source + routing
    assert "signal-geometry" not in source + routing


def test_production_splash_preserves_layout_core_and_entry_contract():
    source = _read(SPLASH)
    required = [
        "#governance{left:78px;top:91px}",
        "#routing{right:78px;top:91px}",
        "left:642px;top:248px;width:388px;height:390px",
        "transform:scale(.88)",
        "transform:scale(1.045)",
        "Enter Maestro",
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "window.location.href = '/login'",
        "const fit_rule='reference-cover-1672x941'",
        "@media(prefers-reduced-motion:reduce)",
    ]
    assert not [marker for marker in required if marker not in source]
