from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "processual_api" / "static"
SPLASH = STATIC_ROOT / "splash.html"
PROOF = STATIC_ROOT / "splash_orchestration_proof.html"
MODEL = STATIC_ROOT / "splash_routing_model.js"
ROUTING = STATIC_ROOT / "splash_routing.js"
LEGACY_BOARD = STATIC_ROOT / "splash_reference_board.svg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_historical_orchestration_proof_is_retained_but_not_canonical():
    assert PROOF.is_file()
    proof = _read(PROOF)
    assert "maestro_descent_gate_seen" in proof
    assert "Enter Maestro" in proof


def test_canonical_splash_uses_inline_generated_board_and_one_motion_geometry():
    source = _read(SPLASH)
    routing = _read(ROUTING)
    required = [
        'id="pcb-board"',
        'id="pcb-routes"',
        'id="pcb-branches"',
        'id="pcb-terminals"',
        'id="pcb-pulses"',
        'type="module" src="./splash_routing.js"',
        "getTotalLength()",
        "getPointAtLength",
        "requestAnimationFrame",
        "reference_outward_module_geometry",
    ]
    combined = source + routing
    assert not [marker for marker in required if marker not in combined]
    assert not LEGACY_BOARD.exists()
    assert 'id="pcb-reference"' not in source
    assert "authoredSignalMap" not in combined


def test_generated_model_is_v20_and_activates_all_four_core_edges():
    model = _read(MODEL)
    assert "A3-splash-routing-v20" in model
    assert "pinCount: 120" in model
    assert "left: 624" in model
    assert "right: 1048" in model
    assert "top: 233" in model
    assert "bottom: 653" in model
    assert "const SIDE_Y = Array.from({ length: 30 }" in model
    assert "const EDGE_X = Array.from({ length: 30 }" in model
    assert "destinationRatioMax: 0.20" in model
    assert "ROUTE_WEIGHTS = Object.freeze({ thick: 1.1, thin: 0.68 })" in model


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


def test_generated_board_keeps_reduced_motion_guards():
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
