import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "processual_api" / "static"
SPLASH = STATIC_ROOT / "splash.html"
PROOF = STATIC_ROOT / "splash_orchestration_proof.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _card_markup(source: str) -> str:
    match = re.search(
        r'<div class="splash-wrap">\s*(<div class="card">.*?</div>)\s*</div>\s*\n\s*<script>',
        source,
        re.DOTALL,
    )
    assert match, "Unable to locate canonical splash card markup"
    return re.sub(r"\s+", " ", match.group(1)).strip()


def test_orchestration_splash_proof_exists_and_preserves_real_card_markup():
    assert PROOF.is_file()
    canonical = _read(SPLASH)
    proof = _read(PROOF)
    assert _card_markup(proof) == _card_markup(canonical)


def test_orchestration_splash_proof_replaces_random_starfield_with_governed_signal_board():
    source = _read(PROOF)
    required = [
        'id="orchestration-board"',
        'id="board-canvas"',
        "buildBoardPaths",
        "pointOnPolyline",
        "BOARD_PALETTE",
        "feedback",
        "prefers-reduced-motion:reduce",
        "reduceMotion.matches",
        "requestAnimationFrame(drawBoard)",
    ]
    forbidden = [
        "class Particle",
        "drawParticles()",
        "const COUNT = 80",
    ]
    missing = [marker for marker in required if marker not in source]
    present_forbidden = [marker for marker in forbidden if marker in source]
    assert not missing, f"Missing orchestration-board proof markers: {missing}"
    assert not present_forbidden, f"Legacy particle-field markers still present: {present_forbidden}"


def test_orchestration_splash_proof_keeps_descent_gate_contract():
    source = _read(PROOF)
    required = [
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "sessionStorage.setItem",
        "window.location.href = '/login'",
        "All systems operational.",
        "Enter Maestro",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing descent-gate contract markers: {missing}"


def test_orchestration_board_paths_are_anchored_to_live_card_geometry():
    source = _read(PROOF)
    required = [
        "boardCard.getBoundingClientRect()",
        "rect.left",
        "rect.right",
        "rect.top",
        "rect.bottom",
        "window.addEventListener('resize',restartBoard",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Board is not anchored to live card geometry: {missing}"


def test_orchestration_splash_proof_keeps_mobile_and_reduced_motion_guards():
    source = _read(PROOF)
    required = [
        "@media(max-width:480px)",
        "@media(prefers-reduced-motion:reduce)",
        "boardWidth < 760 ? 5 : 9",
        "boardWidth < 760 ? 4 : 7",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing responsive/motion safeguards: {missing}"
