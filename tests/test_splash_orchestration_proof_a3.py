from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "processual_api" / "static"
SPLASH = STATIC_ROOT / "splash.html"
PROOF = STATIC_ROOT / "splash_orchestration_proof.html"
BOARD = STATIC_ROOT / "splash_reference_board.svg"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_historical_orchestration_proof_is_retained_but_not_canonical():
    assert PROOF.is_file()
    proof = _read(PROOF)
    assert "maestro_descent_gate_seen" in proof
    assert "Enter Maestro" in proof


def test_canonical_splash_uses_authored_board_plus_pulse_only_overlay():
    source = _read(SPLASH)
    required = [
        'id="pcb-reference"',
        'src="./splash_reference_board.svg"',
        'id="signal-svg"',
        "rebuildSignals",
        "getTotalLength",
        "getPointAtLength",
        "requestAnimationFrame",
        "reference_outward_module_geometry",
        ".signal-geometry{fill:none;stroke:none;pointer-events:none}",
    ]
    forbidden = ["class:'signal-base'", "class:'signal-wake'"]
    assert not [marker for marker in required if marker not in source]
    assert not [marker for marker in forbidden if marker in source]


def test_reference_board_asset_is_v18_measured_and_geometrically_dense():
    board = _read(BOARD)
    assert 'viewBox="0 0 1672 941"' in board
    assert 'data-topology="measured-pin-single-source"' in board
    assert 'data-left-pin-x="624"' in board
    assert 'data-right-pin-x="1048"' in board
    assert 'data-top-pin-y="233"' in board
    assert 'data-bottom-pin-y="653"' in board
    assert board.count('data-route="') >= 70
    assert board.count("<circle") >= 40


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


def test_hybrid_board_keeps_reduced_motion_guards():
    source = _read(SPLASH)
    required = [
        "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',rebuildSignals)",
        ".pulse{display:none}",
    ]
    assert not [marker for marker in required if marker not in source]
