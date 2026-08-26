import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
TRACE = STATIC / "splash_reference_routes.js"
ROUTING = STATIC / "splash_routing.js"
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_fidelity_contract_a3.json"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_contract_targets_v22_pixel_traced_reference():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v22"
    assert contract["architecture"]["mode"] == "inline-pixel-traced-reference-routing"
    assert contract["architecture"]["reference_trace_required"] is True
    assert contract["architecture"]["procedural_route_generator_forbidden"] is True
    assert contract["pcb"]["topology"] == "pixel-traced-reference-segments"
    assert contract["pcb"]["reference_segment_count"] == 166
    assert contract["pcb"]["route_weight_classes_exact"] == 2


def test_trace_data_matches_reference_image_measurements():
    trace = _read(TRACE)
    assert '"source_width":970' in trace
    assert '"source_height":560' in trace
    assert '"core_reference_px":[339,126,623,351]' in trace
    assert '"segment_count":166' in trace
    assert trace.count('"id":"ref-') == 166


def test_runtime_warps_reference_pixels_to_the_live_core_envelope():
    routing = _read(ROUTING)
    required = [
        "REF.core_reference_px",
        "left: 624, top: 233, right: 1048, bottom: 653",
        "function mapAxis(",
        "function mapPoint([x, y])",
        "segment.points.map(mapPoint)",
        "'data-source': 'pivot-reference-image'",
    ]
    assert not [marker for marker in required if marker not in routing]


def test_procedural_v21_route_generator_is_gone():
    routing = _read(ROUTING)
    forbidden = [
        "PINS.forEach(renderRoute)",
        "sideFieldRoute",
        "sideDestinationRoute",
        "verticalFieldRoute",
        "buildBranch(pin",
        "corridorY(pin)",
    ]
    assert not [marker for marker in forbidden if marker in routing]


def test_motion_uses_the_exact_visible_reference_paths_and_identity_is_preserved():
    source = _read(SPLASH)
    routing = _read(ROUTING)
    required = [
        "item.route.getTotalLength()",
        "item.route.getPointAtLength",
        'class="maestro-emblem"',
        'class="brand-word">MAESTRO<b>.</b>',
        'class="core-emblem"',
        "Govern • Supervise • Calibrate • Orchestrate",
        "Enter Maestro",
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "window.location.href = '/login'",
        "transform:scale(1.045)",
        "transform:scale(.88)",
        "const fit_rule='reference-cover-1672x941'",
        "@media(prefers-reduced-motion:reduce)",
    ]
    combined = source + routing
    assert not [marker for marker in required if marker not in combined]
    assert "authoredSignalMap" not in combined
    assert re.search(r"[\u0600-\u06FF]", source) is None
