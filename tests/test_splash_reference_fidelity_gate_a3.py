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
    assert contract["contract_version"] == "A3-splash-reference-v10"
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
        "fit_rule": "reference-cover-1672x941",
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
    required_board_markers = [
        '<ellipse cx="836" cy="452"',
        'id="dotsC"',
        'id="dotsA"',
        'id="dotsV"',
        'sculpted module frame rails',
        'long ambient branches that intentionally do not terminate at cards',
        'asymmetric right-side ambient fabric: intentionally not mirrored',
        'central-origin surface merge network',
        'asymmetric right merge fabric',
        'organic micro-topology islands',
        'core rim integration: nested processor rails and pin landing geometry',
        'crown breakout with scattered hotspots; top rings deliberately removed',
        'execution radial fabric and bottom telemetry backplane',
        'explicit wide-spread luminous via network / dense page-wide node matrices',
        'scattered crown hotspots, not circular ring clusters',
        'pin landing nodes',
    ]
    assert not [marker for marker in required_board_markers if marker not in board]
    assert 'ring via clusters' not in board
    assert pcb["nonterminating_ambient_branches_required"] is True
    assert pcb["distributed_dot_matrices_required"] is True
    assert pcb["sculpted_module_frame_rails_required"] is True
    assert pcb["core_origin_merge_network_required"] is True
    assert pcb["dead_end_surface_runs_required"] is True
    assert pcb["wide_luminous_node_field_required"] is True
    assert pcb["core_rim_integration_required"] is True
    assert pcb["processor_pin_landing_nodes_required"] is True
    assert pcb["execution_radial_fabric_required"] is True
    assert pcb["telemetry_backplane_required"] is True
    assert pcb["organic_micro_topology_required"] is True
    assert pcb["asymmetric_fabric_required"] is True
    assert pcb["top_ring_clusters_forbidden"] is True
    assert pcb["crown_hotspot_clusters_required"] is True
    assert pcb["irregular_branching_required"] is True


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


def test_motion_semantics_remain_autonomous_directional_and_asymmetric():
    source = _source()
    required = [
        "governance:'outbound'", "policy:'outbound'", "routing:'outbound'",
        "supervision:'inbound'", "feedback:'inbound'", "calibration:'bidirectional'",
        "orchestration:'bidirectional'", "control:'roundtrip'", "execution:'downstream'",
        "signal-wake", "node-bloom", "destination-ack", "p3=E('circle'",
        "M1276 162 H1214 L1188 146", "M1276 339 H1221 L1190 365",
    ]
    forbidden = ["mouseenter", "mouseleave", "focusRoute(", "classList.toggle('dim'"]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]
    assert _contract()["motion"]["left_right_signal_geometry_must_differ"] is True


def test_accessibility_and_viewport_fill_remain_intact():
    source = _source()
    required = [
        "@media(prefers-reduced-motion:reduce)", ".pulse{display:none}", 'tabindex="0"',
        "const fit_rule='reference-cover-1672x941'", "Math.max(viewportWidth/1672,viewportHeight/941)",
        "reduceMotion.addEventListener?.('change',rebuildSignals)",
    ]
    assert not [m for m in required if m not in source]
    assert _contract()["viewport"]["fill_browser_area_required"] is True
    assert _contract()["viewport"]["letterbox_forbidden"] is True
