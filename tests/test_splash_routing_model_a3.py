from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
MODEL = STATIC / "splash_routing_model.js"
ROUTING = STATIC / "splash_routing.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_v20_model_uses_one_record_per_visible_pin_family():
    source = _read(MODEL)
    assert "A3-splash-routing-v20" in source
    assert "pinCount: 120" in source
    assert "const SIDE_Y = Array.from({ length: 30 }" in source
    assert "const EDGE_X = Array.from({ length: 30 }" in source
    assert "export const PINS = Object.freeze(buildPins())" in source
    assert "id: `${side}-${String(i + 1).padStart(2, '0')}`" in source


def test_destination_routes_are_explicitly_the_minority():
    source = _read(MODEL)
    assert "destinationRatioMax: 0.20" in source
    side_destination_indexes = re.findall(r"indexes: \[([^\]]+)\]", source)
    assert len(side_destination_indexes) == 8
    assert "[13, 14, 15].includes(i)" in source


def test_model_has_exactly_two_route_weights():
    source = _read(MODEL)
    match = re.search(r"ROUTE_WEIGHTS = Object\.freeze\(\{([^}]+)\}\)", source)
    assert match
    weights = re.findall(r"(thick|thin):", match.group(1))
    assert weights == ["thick", "thin"]
    assert "micro" not in match.group(1)


def test_short_medium_long_bands_and_selective_motion_are_bounded():
    source = _read(MODEL)
    for marker in ["short: [82, 126]", "medium: [146, 218]", "long: [236, 322]"]:
        assert marker in source
    assert "pulseRatioMax: 0.20" in source
    assert "branchRatioMax: 0.26" in source
    assert "function pulseFor(i)" in source
    assert "i % 8 === 0 || i % 17 === 0" in source
    assert "function branchFor(i)" in source


def test_routing_generator_uses_the_model_as_single_geometry_source():
    source = _read(ROUTING)
    required = [
        "import { CORE, STAGE, COLORS, ROUTE_WEIGHTS, CONTRACT, PINS }",
        "PINS.forEach(renderRoute)",
        "function buildSideRoute",
        "function buildVerticalRoute",
        "function buildBranch",
        "getTotalLength()",
        "getPointAtLength",
        "data-route-id",
        "data-pin-id",
    ]
    assert not [marker for marker in required if marker not in source]
    assert "authoredSignalMap" not in source
