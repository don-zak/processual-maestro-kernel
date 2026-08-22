import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
BOARD = STATIC / "splash_reference_board.svg"
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_fidelity_contract_a3.json"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def _board() -> str:
    return BOARD.read_text(encoding="utf-8")


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_splash_reference_contract_is_explicit_and_requires_99_percent():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v5"
    assert contract["minimum_score"] >= 99
    assert contract["score_total"] == 100
    assert sum(contract["scoring"].values()) == 100
    assert contract["architecture"]["mode"] == "authored-svg-dom-hybrid"


def test_reference_stage_and_outward_geometry_are_locked():
    contract = _contract()
    assert contract["reference_stage"] == {
        "width": 1672,
        "height": 941,
        "aspect_ratio": "1672:941",
        "fit_rule": "reference-contain-1672x941",
    }
    layout = contract["logical_layout"]
    assert layout["core_bounds"] == {"x": 642, "y": 248, "w": 388, "h": 390, "tolerance_px": 16}
    assert layout["modules"]["governance"]["x"] == 78
    assert layout["modules"]["routing"]["x"] == 1276


def test_authored_board_asset_meets_reference_density_gate():
    board = _board()
    pcb = _contract()["pcb"]
    assert board.count("<path") >= pcb["authored_paths_min"]
    assert board.count("<circle") >= pcb["authored_nodes_min"]
    for marker in ['stroke="#36bfff"', 'stroke="#e59a20"', 'stroke="#23d8c8"', 'stroke="#c16fff"']:
        assert marker in board
    assert '<ellipse cx="836" cy="452"' in board


def test_hybrid_architecture_uses_static_reference_fabric_plus_live_signals():
    source = _source()
    required = [
        'src="./splash_reference_board.svg"', 'id="signal-svg"', "authoredSignalMap",
        "function registerSignal(", "function rebuildSignals()", "function animate(now)",
        "getTotalLength", "getPointAtLength", "requestAnimationFrame(animate)",
    ]
    forbidden = ["function pcb(", "function drawSideFabric(", "function regionalFabric(", "drawAmbientBoard("]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_core_entry_contract_is_non_compensable():
    source = _source()
    for marker in _contract()["mandatory_core_contract"]["preserve_markers"]:
        assert marker in source
    assert "background:rgba(22,29,42,.68)" in source
    assert "--amber:#f5a623" in source


def test_motion_semantics_remain_autonomous_and_directional():
    source = _source()
    required = [
        "governance:'outbound'", "policy:'outbound'", "routing:'outbound'",
        "supervision:'inbound'", "feedback:'inbound'", "calibration:'bidirectional'",
        "orchestration:'bidirectional'", "control:'roundtrip'", "execution:'downstream'",
        "signal-wake", "node-bloom", "destination-ack", "p3=E('circle'",
    ]
    forbidden = ["mouseenter", "mouseleave", "focusRoute(", "classList.toggle('dim'"]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_accessibility_and_reference_fit_remain_intact():
    source = _source()
    required = [
        "@media(prefers-reduced-motion:reduce)", ".pulse{display:none}", 'tabindex="0"',
        "const fit_rule='reference-contain-1672x941'", "Math.min(viewportWidth/1672,viewportHeight/941)",
        "reduceMotion.addEventListener?.('change',rebuildSignals)",
    ]
    assert not [m for m in required if m not in source]
