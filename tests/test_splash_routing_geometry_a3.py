from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
TRACE = STATIC / "splash_reference_routes.js"
ROUTING = STATIC / "splash_routing.js"
LEGACY_BOARD = STATIC / "splash_reference_board.svg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_legacy_generated_routing_is_not_canonical_anymore():
    source = _read(SPLASH)
    routing = _read(ROUTING)
    assert not LEGACY_BOARD.exists()
    assert 'id="pcb-reference"' not in source
    assert "authoredSignalMap" not in source + routing
    assert "PINS.forEach(renderRoute)" not in routing
    assert "sideFieldRoute" not in routing
    assert "verticalFieldRoute" not in routing


def test_reference_pixels_are_piecewise_mapped_around_the_real_core():
    routing = _read(ROUTING)
    required = [
        "const [REF_LEFT, REF_TOP, REF_RIGHT, REF_BOTTOM] = REF.core_reference_px",
        "const TARGET = Object.freeze({ left: 624, top: 233, right: 1048, bottom: 653 })",
        "function mapAxis(",
        "function mapPoint([x, y])",
        "REF.source_width",
        "REF.source_height",
        "STAGE.width",
        "STAGE.height",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_each_traced_segment_becomes_one_visible_svg_path():
    trace = _read(TRACE)
    routing = _read(ROUTING)
    assert '"segment_count":166' in trace
    assert "REFERENCE_ROUTE_TRACE.segments.forEach((segment, index) =>" in routing
    assert "id: `reference-${segment.id}`" in routing
    assert "d: pointsToD(points)" in routing
    assert "'data-route-id': segment.id" in routing
    assert "'data-source': 'pivot-reference-image'" in routing


def test_only_two_visible_route_weights_are_used():
    routing = _read(ROUTING)
    assert "const ROUTE_WEIGHTS = Object.freeze({ thick: 1.08, thin: 0.66 })" in routing
    assert "pcb-route-${weight}" in routing
    assert "ROUTE_WEIGHTS[weight]" in routing
    assert "micro" not in routing


def test_terminals_and_pulses_use_the_exact_traced_path_geometry():
    routing = _read(ROUTING)
    assert "const [x, y] = points[points.length - 1]" in routing
    assert "item.route.getTotalLength()" in routing
    assert "item.route.getPointAtLength" in routing
    assert "authoredSignalMap" not in routing
    assert "signal-geometry" not in routing
