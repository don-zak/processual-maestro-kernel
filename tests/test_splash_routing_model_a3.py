from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
TRACE = STATIC / "splash_reference_routes.js"
ROUTING = STATIC / "splash_routing.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_reference_trace_is_derived_from_the_pivot_image_pixels():
    trace = _read(TRACE)
    assert "REFERENCE_ROUTE_TRACE" in trace
    assert '"source_width":970' in trace
    assert '"source_height":560' in trace
    assert '"core_reference_px":[339,126,623,351]' in trace
    assert '"segment_count":166' in trace
    assert trace.count('"id":"ref-') == 166


def test_reference_trace_preserves_route_color_families():
    trace = _read(TRACE)
    for color in ["cyan", "teal", "lime", "amber", "violet"]:
        assert f'"color":"{color}"' in trace


def test_runtime_uses_reference_trace_as_the_canonical_geometry_source():
    routing = _read(ROUTING)
    required = [
        "import { REFERENCE_ROUTE_TRACE } from './splash_reference_routes.js'",
        "REFERENCE_ROUTE_TRACE.segments.forEach",
        "segment.points.map(mapPoint)",
        "'data-source': 'pivot-reference-image'",
        "A3-splash-reference-pixeltrace-v22",
    ]
    assert not [marker for marker in required if marker not in routing]
    assert "PINS.forEach(renderRoute)" not in routing
    assert "sideFieldRoute" not in routing
    assert "verticalFieldRoute" not in routing
