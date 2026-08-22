import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "processual_api" / "static"
SPLASH = STATIC_ROOT / "splash.html"
PROOF = STATIC_ROOT / "splash_orchestration_proof.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _card_markup(source: str) -> str:
    start = source.find('<div class="card">')
    assert start >= 0, "Unable to locate canonical splash card markup"
    depth = 0
    cursor = start
    token = re.compile(r"<div\b[^>]*>|</div>")
    for match in token.finditer(source, start):
        if match.group(0).startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                normalized = re.sub(r"\s+", " ", source[start : match.end()]).strip()
                return re.sub(r">\s+<", "><", normalized)
        cursor = match.end()
    raise AssertionError(f"Unclosed canonical splash card near offset {cursor}")


def test_orchestration_splash_proof_exists_and_preserves_real_card_markup():
    assert PROOF.is_file()
    canonical = _read(SPLASH)
    proof = _read(PROOF)
    assert _card_markup(proof) == _card_markup(canonical)


def test_living_orchestration_board_has_reference_semantic_modules():
    source = _read(PROOF)
    required = [
        'id="living-board"',
        'id="signal-svg"',
        'data-module="governance"',
        'data-module="supervision"',
        'data-module="calibration"',
        'data-module="orchestration"',
        'data-module="routing"',
        'data-module="policy"',
        'data-module="feedback"',
        'data-module="control"',
        'id="execution-zone"',
        'class="module left-module"',
        'class="module right-module"',
        'class="core-pins"',
        'class="core-top-pins"',
        'class="core-bottom-pins"',
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing reference-oriented living-board modules: {missing}"


def test_living_orchestration_board_uses_dense_svg_circuitry_not_particle_field():
    source = _read(PROOF)
    required = [
        "rebuildSignals",
        "orthogonalPath",
        "addAmbientTraces",
        "getTotalLength",
        "getPointAtLength",
        "trace bus",
        "trace micro",
        "class:'pulse'",
        "routeRecords",
        "selectRoute",
        "for(let i=-2;i<=2;i++)",
    ]
    forbidden = [
        "class Particle",
        "drawParticles()",
        "const COUNT = 80",
        'id="board-canvas"',
    ]
    missing = [marker for marker in required if marker not in source]
    present_forbidden = [marker for marker in forbidden if marker in source]
    assert not missing, f"Missing dense SVG orchestration markers: {missing}"
    assert not present_forbidden, f"Legacy particle/canvas markers still present: {present_forbidden}"


def test_living_orchestration_routes_are_anchored_to_live_card_and_modules():
    source = _read(PROOF)
    required = [
        "const cardRect=relativeRect(card)",
        "const moduleRect=relativeRect(module)",
        "const a=anchor(cardRect,moduleCenter)",
        "const b=anchor(moduleRect,cardCenter)",
        "window.addEventListener('resize'",
        "rebuildSignals",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"SVG routes are not anchored to live geometry: {missing}"


def test_living_orchestration_modules_expose_interactive_route_focus():
    source = _read(PROOF)
    required = [
        "module.addEventListener('mouseenter'",
        "module.addEventListener('mouseleave'",
        "module.addEventListener('focus'",
        "module.addEventListener('blur'",
        "executionZone.addEventListener('mouseenter'",
        "classList.toggle('is-active'",
        "classList.toggle('active'",
        "classList.toggle('dim'",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing interactive route-focus behavior: {missing}"


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


def test_living_orchestration_board_keeps_responsive_and_reduced_motion_guards():
    source = _read(PROOF)
    required = [
        "@media(max-width:1240px)",
        "@media(max-width:920px)",
        "@media(max-width:560px)",
        "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',rebuildSignals)",
        ".pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing responsive/motion safeguards: {missing}"
