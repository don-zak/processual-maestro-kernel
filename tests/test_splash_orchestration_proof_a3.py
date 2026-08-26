from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "processual_api" / "static"
SPLASH = STATIC_ROOT / "splash.html"
PROOF = STATIC_ROOT / "splash_orchestration_proof.html"
TRACE = STATIC_ROOT / "splash_reference_routes.js"
ROUTING = STATIC_ROOT / "splash_routing.js"
LEGACY_BOARD = STATIC_ROOT / "splash_reference_board.svg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_historical_orchestration_proof_is_retained_but_not_canonical():
    assert PROOF.is_file()
    proof = _read(PROOF)
    assert "maestro_descent_gate_seen" in proof
    assert "Enter Maestro" in proof


def test_canonical_splash_uses_pixel_traced_reference_and_one_motion_geometry():
    source = _read(SPLASH)
    trace = _read(TRACE)
    routing = _read(ROUTING)
    required = [
        'id="pcb-board"',
        'id="pcb-routes"',
        'id="pcb-terminals"',
        'id="pcb-pulses"',
        'type="module" src="./splash_routing.js"',
        "REFERENCE_ROUTE_TRACE.segments.forEach",
        "getTotalLength()",
        "getPointAtLength",
        "requestAnimationFrame",
        "A3-splash-reference-pixeltrace-v22",
    ]
    combined = source + trace + routing
    assert not [marker for marker in required if marker not in combined]
    assert not LEGACY_BOARD.exists()
    assert 'id="pcb-reference"' not in source
    assert "authoredSignalMap" not in combined
    assert "PINS.forEach(renderRoute)" not in routing


def test_reference_trace_records_the_source_image_geometry():
    trace = _read(TRACE)
    assert '"source_width":970' in trace
    assert '"source_height":560' in trace
    assert '"core_reference_px":[339,126,623,351]' in trace
    assert '"segment_count":166' in trace


def test_canonical_splash_keeps_descent_gate_contract():
    source = _read(SPLASH)
    required = [
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "sessionStorage.setItem",
        "window.location.href = '/login'",
        "All systems operational.",
        "Enter Maestro",
    ]
    assert not [marker for marker in required if marker not in source]


def test_reference_board_keeps_reduced_motion_guards():
    source = _read(SPLASH)
    routing = _read(ROUTING)
    required = [
        "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change', restartMotion)",
        ".pcb-pulse{display:none}",
    ]
    combined = source + routing
    assert not [marker for marker in required if marker not in combined]
