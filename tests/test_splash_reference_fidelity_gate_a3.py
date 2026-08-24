import json
import re
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
    assert contract["contract_version"] == "A3-splash-reference-v13"
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
    assert layout["side_module_visual_scale"] == 0.90
    assert layout["segmented_variable_weight_card_rails_required"] is True


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
        'balanced density envelope / visual breathing corridors',
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
    assert pcb["balanced_density_required"] is True
    assert pcb["visual_breathing_corridors_required"] is True
    assert pcb["route_colored_processor_teeth_required"] is True


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


def test_original_maestro_identity_and_english_only_copy_are_locked():
    source = _source()
    branding = _contract()["branding"]
    assert branding["original_maestro_emblem_required"] is True
    assert branding["header_wordmark_required"] is True
    assert branding["core_emblem_required"] is True
    assert branding["english_only_copy_required"] is True
    assert branding["concise_copy_required"] is True
    required = [
        'class="maestro-emblem"', 'class="brand-word">MAESTRO<b>.</b>', 'class="core-emblem"',
        "Govern • Supervise • Calibrate • Orchestrate",
        "Centralized AI policy, safety and performance control.",
        "Human oversight for agents, tasks and decisions.",
        "Model tuning and profile optimization for best-fit performance.",
        "Task and agent coordination across scalable workflows.",
        "Intelligent routing for requests, tasks and optimal agent selection.",
        "Advanced policy enforcement for rules, approvals and automated decisions.",
        "Continuous feedback and learning for improved outcomes.",
        "Authority, access and guardrail controls.",
        "Controlled real-time execution",
    ]
    assert not [m for m in required if m not in source]
    assert re.search(r"[\u0600-\u06FF]", source) is None


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


def test_accessibility_viewport_fill_and_safe_bands_remain_intact():
    source = _source()
    viewport = _contract()["viewport"]
    required = [
        "@media(prefers-reduced-motion:reduce)", ".pulse{display:none}", 'tabindex="0"',
        "const fit_rule='reference-cover-1672x941'", "Math.max(viewportWidth/1672,viewportHeight/941)",
        "const visibleWorldWidth=viewportWidth/scale,visibleWorldHeight=viewportHeight/scale",
        "const cropX=Math.max(0,(1672-visibleWorldWidth)/2),cropY=Math.max(0,(941-visibleWorldHeight)/2)",
        "--header-drop", "--footer-lift", "--telemetry-lift", "--safe-x",
        "reduceMotion.addEventListener?.('change',rebuildSignals)",
    ]
    assert not [m for m in required if m not in source]
    assert viewport["fill_browser_area_required"] is True
    assert viewport["letterbox_forbidden"] is True
    assert viewport["adaptive_safe_bands_required"] is True
    assert viewport["header_footer_must_remain_visible_under_cover"] is True
    assert viewport["telemetry_must_remain_visible_under_cover"] is True


def test_route_colored_processor_teeth_are_explicit_and_vivid():
    source = _source()
    required = [
        "/* route-colored processor teeth */",
        "linear-gradient(180deg,#21c9ff 0 24%,#22dfcd 24% 49%,#a7d67b 49% 74%,#c16fff 74% 100%)",
        "linear-gradient(180deg,#f1a21d 0 49%,#23d8c8 49% 75%,#c16fff 75% 100%)",
        "linear-gradient(90deg,#20c7ff 0 24%,#1ee0cf 24% 44%,#33cfff 44% 50%,#f0a21f 50% 80%,#ffc24d 80% 100%)",
        "linear-gradient(90deg,#20c7ff 0 22%,#23d8c8 22% 34%,#c16fff 34% 48%,#36bfff 48% 57%,#f0a21f 57% 72%,#c16fff 72% 100%)",
    ]
    assert not [m for m in required if m not in source]
