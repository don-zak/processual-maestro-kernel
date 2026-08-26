from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
MODEL = STATIC / "splash_routing_model.js"
ROUTING = STATIC / "splash_routing.js"
LEGACY_BOARD = STATIC / "splash_reference_board.svg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_legacy_external_routing_asset_is_not_canonical_anymore():
    source = _read(SPLASH)
    assert 'id="pcb-reference"' not in source
    assert "splash_reference_board.svg" not in source
    assert "authoredSignalMap" not in source
    assert 'id="pcb-board"' in source
    assert 'id="pcb-routes"' in source
    assert 'id="pcb-branches"' in source
    assert 'id="pcb-terminals"' in source
    assert 'id="pcb-pulses"' in source
    assert 'src="./splash_routing.js"' in source


def test_every_root_route_is_created_from_a_pin_record():
    source = _read(ROUTING)
    assert "PINS.forEach(renderRoute)" in source
    assert "'data-pin-id': pin.id" in source
    assert "id: `route-${pin.id}`" in source
    assert "buildRoute(pin)" in source


def test_side_routes_have_an_explicit_aligned_breakout_before_spread():
    source = _read(ROUTING)
    model = _read(MODEL)
    assert "sideStem: 46" in model
    assert "verticalStem: 38" in model
    assert "const stemX = pin.x + dir * CONTRACT.sideStem" in source
    assert "const points = [[pin.x, pin.y], [stemX, pin.y]]" in source
    assert "const stemY = pin.y + dir * CONTRACT.verticalStem" in source
    assert "const points = [[pin.x, pin.y], [pin.x, stemY]]" in source


def test_progressive_spread_uses_multiple_stages_and_non_cloned_variants():
    source = _read(ROUTING)
    for marker in [
        "function spreadOffset(pin, stage)",
        "const o1 = spreadOffset(pin, 1)",
        "const o2 = spreadOffset(pin, 2)",
        "const o3 = spreadOffset(pin, 3)",
        "if (pin.variant === 0)",
        "if (pin.variant === 1)",
        "if (pin.variant === 2)",
        "if (pin.variant === 3)",
        "if (pin.variant === 4)",
    ]:
        assert marker in source


def test_branches_are_parent_linked_and_terminals_use_real_endpoints():
    source = _read(ROUTING)
    assert "'data-branch-parent': pin.id" in source
    assert "const [x, y] = points[points.length - 1]" in source
    assert "terminalsLayer.append(terminal(points, color))" in source
    assert "terminalsLayer.append(terminal(branchPoints, color, true))" in source


def test_pulses_follow_the_exact_visible_route_elements():
    source = _read(ROUTING)
    assert "pulseRoutes.push({ pin, route, color })" in source
    assert "item.route.getTotalLength()" in source
    assert "item.route.getPointAtLength" in source
    assert "authoredSignalMap" not in source
    assert "signal-geometry" not in source


def test_no_third_route_weight_is_generated():
    source = _read(ROUTING)
    assert "ROUTE_WEIGHTS[pin.weight]" in source
    assert "ROUTE_WEIGHTS.thin" in source
    assert "micro" not in source
