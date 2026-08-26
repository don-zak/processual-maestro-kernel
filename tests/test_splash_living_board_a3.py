from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
TRACE = STATIC / "splash_reference_routes.js"
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
    for marker in ['id="pcb-board"', 'id="pcb-routes"', 'id="pcb-branches"', 'id="pcb-terminals"', 'id="pcb-pulses"']:
        assert marker in source
    assert 'type="module" src="./splash_routing.js"' in source


def test_reference_trace_is_the_visual_routing_authority():
    trace = _read(TRACE)
    routing = _read(ROUTING)
    assert '"segment_count":166' in trace
    assert "REFERENCE_ROUTE_TRACE.segments.forEach" in routing
    assert "A3-splash-reference-pixeltrace-v22" in routing
    assert "'data-source': 'pivot-reference-image'" in routing
    assert "PINS.forEach(renderRoute)" not in routing


def test_exactly_two_route_weight_classes_are_rendered():
    routing = _read(ROUTING)
    assert "const ROUTE_WEIGHTS = Object.freeze({ thick: 1.08, thin: 0.66 })" in routing
    assert "pcb-route-${weight}" in routing
    assert "ROUTE_WEIGHTS[weight]" in routing
    assert "micro" not in routing


def test_pixel_trace_is_core_anchored_and_piecewise_warped():
    routing = _read(ROUTING)
    required = [
        "REF.core_reference_px",
        "left: 624, top: 233, right: 1048, bottom: 653",
        "function mapAxis(",
        "function mapPoint([x, y])",
        "REF.source_width",
        "REF.source_height",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_terminal_beacons_are_bound_to_real_traced_endpoints():
    routing = _read(ROUTING)
    assert "const [x, y] = points[points.length - 1]" in routing
    assert "terminalsLayer.append(terminal(points, color" in routing


def test_pulses_follow_selected_visible_reference_routes():
    source = _read(SPLASH)
    routing = _read(ROUTING)
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
