from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
BLUEPRINT = STATIC / "splash_reference_blueprint.js"
MODEL = STATIC / "splash_routing_model.js"
ROUTING = STATIC / "splash_routing.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v21_model_is_reference_blueprint_driven():
    blueprint = _read(BLUEPRINT)
    model = _read(MODEL)
    assert "A3-splash-reference-blueprint-v21" in blueprint
    assert "source: 'pivot-reference-image'" in blueprint
    assert "import { REFERENCE_BLUEPRINT, corridorFor }" in model
    assert "version: REFERENCE_BLUEPRINT.version" in model
    assert "pinCount: 120" in model
    assert "const SIDE_Y = Array.from({ length: 30 }" in model
    assert "const EDGE_X = Array.from({ length: 30 }" in model
    assert "export const PINS = Object.freeze(buildPins())" in model


def test_destination_routes_are_explicitly_the_minor_reference_population():
    blueprint = _read(BLUEPRINT)
    model = _read(MODEL)
    assert "destinationRatioMax: 0.16" in blueprint
    assert "modulePins" in blueprint
    assert "left: Object.freeze([2, 6, 10, 13, 17, 20, 24, 28])" in blueprint
    assert "right: Object.freeze([1, 5, 9, 12, 16, 20, 24, 27])" in blueprint
    assert "bottom: Object.freeze([14, 15])" in blueprint
    assert "destinationRatioMax: REFERENCE_BLUEPRINT.destinationRatioMax" in model


def test_blueprint_has_exactly_two_route_weights():
    blueprint = _read(BLUEPRINT)
    assert "routeWeights: Object.freeze({ thick: 1.08, thin: 0.66 })" in blueprint
    assert "micro" not in blueprint


def test_reference_reach_bands_are_side_top_bottom_specific():
    blueprint = _read(BLUEPRINT)
    for marker in [
        "sideReach: Object.freeze({ short: [58, 86], medium: [98, 136], long: [146, 188] })",
        "topReach: Object.freeze({ short: [42, 66], medium: [76, 108], long: [118, 164] })",
        "bottomReach: Object.freeze({ short: [38, 58], medium: [64, 92], long: [98, 132] })",
    ]:
        assert marker in blueprint
    assert "pulseRatioMax: 0.18" in blueprint
    assert "branchRatioMax: 0.24" in blueprint


def test_routing_generator_consumes_blueprint_and_model_as_single_geometry_source():
    source = _read(ROUTING)
    required = [
        "import { CORE, STAGE, COLORS, ROUTE_WEIGHTS, CONTRACT, PINS }",
        "import { REFERENCE_BLUEPRINT }",
        "PINS.forEach(renderRoute)",
        "function sideFieldRoute",
        "function sideDestinationRoute",
        "function verticalFieldRoute",
        "function buildBranch",
        "getTotalLength()",
        "getPointAtLength",
        "data-route-id",
        "data-pin-id",
    ]
    assert not [marker for marker in required if marker not in source]
    assert "authoredSignalMap" not in source
