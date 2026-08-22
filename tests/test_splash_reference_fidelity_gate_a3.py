import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "processual_api" / "static" / "splash.html"
CONTRACT = ROOT / "tests" / "fixtures" / "splash_reference_fidelity_contract_a3.json"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def _missing(source: str, markers: list[str]) -> list[str]:
    return [marker for marker in markers if marker not in source]


def _category_score(source: str, markers: list[str], weight: int) -> tuple[float, list[str]]:
    if not markers:
        return float(weight), []
    missing = _missing(source, markers)
    matched = len(markers) - len(missing)
    return weight * (matched / len(markers)), missing


def test_splash_reference_contract_is_explicit_and_requires_99_percent():
    contract = _contract()
    assert contract["contract_version"] == "A3-splash-reference-v2"
    assert contract["score_total"] == 100
    assert contract["minimum_score"] >= 99
    assert sum(contract["scoring"].values()) == 100
    assert contract["reference_stage"]["width"] == 1440
    assert contract["reference_stage"]["height"] == 1080
    assert contract["reference_stage"]["fit_rule"] == "full-bleed-fluid-width"


def test_splash_core_entry_card_is_a_non_compensable_gate():
    source = _source()
    contract = _contract()["mandatory_core_contract"]
    missing_content = _missing(source, contract["preserve_card_markers"])
    missing_color = _missing(source, contract["preserve_color_markers"])
    assert contract["preserve_dark_card"] is True
    assert not missing_content, (
        "Central Maestro entry card contract changed; fidelity points cannot compensate for this: "
        f"{missing_content}"
    )
    assert not missing_color, (
        "Central Maestro entry card color/identity changed; this is forbidden: "
        f"{missing_color}"
    )


def test_splash_reference_geometry_contract_is_machine_readable():
    contract = _contract()["logical_layout"]
    assert contract["core_bounds"] == {
        "x": 480,
        "y": 295,
        "w": 480,
        "h": 440,
        "tolerance_px": 36,
    }
    assert contract["execution_center"] == {"x": 720, "y": 850, "tolerance_px": 36}
    assert set(contract["modules"]) == {
        "governance", "supervision", "calibration", "orchestration",
        "routing", "policy", "feedback", "control",
    }
    assert {module["side"] for module in contract["modules"].values()} == {"left", "right"}
    assert all(module["w"] == 315 for module in contract["modules"].values())
    assert all(module["h"] == 145 for module in contract["modules"].values())


def test_splash_reference_fidelity_score_must_reach_99_percent():
    source = _source()
    contract = _contract()
    scoring = contract["scoring"]
    categories: dict[str, tuple[list[str], int]] = {
        "stage_geometry": (contract["reference_stage"]["required_markers"], scoring["stage_geometry"]),
        "core_preservation": (
            contract["mandatory_core_contract"]["preserve_card_markers"]
            + contract["mandatory_core_contract"]["preserve_color_markers"],
            scoring["core_preservation"],
        ),
        "module_geometry_and_hierarchy": ([
            'id="governance"','id="supervision"','id="calibration"','id="orchestration"',
            'id="routing"','id="policy"','id="feedback"','id="control"','id="execution"',
            "secondary_cards_are_nodes_not_dashboard_cards","connector-pad",
        ], scoring["module_geometry_and_hierarchy"]),
        "pcb_density_and_connectivity": (
            contract["pcb"]["required_markers"], scoring["pcb_density_and_connectivity"]
        ),
        "motion_semantics": (
            contract["motion"]["required_markers"] + [
                "governance:'outbound'","policy:'outbound'","routing:'outbound'",
                "supervision:'inbound'","feedback:'inbound'","calibration:'bidirectional'",
                "orchestration:'bidirectional'","control:'roundtrip'","execution:'downstream'",
            ], scoring["motion_semantics"]),
        "telemetry_and_depth": (["top-agent-node","activity-bars","governance-trend","integrity-ring"], scoring["telemetry_and_depth"]),
        "color_and_typography": (
            contract["color_system"]["background_layers"] + contract["color_system"]["cyan_levels"]
            + contract["color_system"]["amber_levels"]
            + ["direction:rtl","var(--display)","var(--mono)"],
            scoring["color_and_typography"],
        ),
        "accessibility_and_responsiveness": ([
            "@media(prefers-reduced-motion:reduce)","tabindex=\"0\"",
            "requestAnimationFrame","addEventListener('resize'","fit_rule",
            "worldWidth=Math.max(1440,viewportWidth/scale)",
        ], scoring["accessibility_and_responsiveness"]),
    }
    total = 0.0
    details: list[str] = []
    for name, (markers, weight) in categories.items():
        score, missing = _category_score(source, markers, weight)
        total += score
        if missing:
            details.append(f"{name}: {score:.2f}/{weight} missing={missing}")
    assert total >= contract["minimum_score"], (
        f"Splash reference fidelity score {total:.2f}/100 is below required {contract['minimum_score']}/100. "
        "The gate is intentionally strict and should remain red until the reference-stage, authored PCB topology, "
        "semantic motion, telemetry, color depth and typography contract are implemented. " + " | ".join(details)
    )


def test_splash_motion_semantics_are_not_decorative_only():
    source = _source()
    motion = _contract()["motion"]
    assert motion["trace_wake_required"] is True
    assert motion["node_bloom_required"] is True
    assert motion["destination_ack_required"] is True
    assert motion["autonomous_motion_required"] is True
    assert motion["pointer_route_interaction_required"] is False
    assert motion["pulse_count_per_active_route_min"] >= 2
    assert motion["pulse_count_per_active_route_max"] <= 4
    missing = _missing(source, motion["required_markers"])
    assert not missing, f"Motion is still decorative rather than semantically governed. Missing: {missing}"
    forbidden = ["mouseenter", "mouseleave", "focusRoute(", "classList.toggle('dim'"]
    present = [marker for marker in forbidden if marker in source]
    assert not present, f"Autonomous landing motion regressed to pointer-driven routing: {present}"


def test_splash_reference_requires_authored_connector_topology_and_full_vertical_networks():
    source = _source()
    pcb = _contract()["pcb"]
    assert pcb["primary_paths_per_subsystem_min"] >= 5
    assert pcb["secondary_paths_per_subsystem_min"] >= 8
    assert pcb["tertiary_paths_per_subsystem_min"] >= 10
    assert pcb["total_visual_paths_per_subsystem_min"] >= 23
    assert pcb["top_vertical_bus_min"] >= 10
    assert pcb["bottom_vertical_bus_min"] >= 10
    assert pcb["ambient_layers_min"] >= 3
    missing = _missing(source, pcb["required_markers"])
    assert not missing, f"Reference-authored connector/PCB topology is incomplete: {missing}"
    assert "function pcb(" not in source, "Generic connector-to-core PCB generator must not return"
    assert "for(let j=-9;j<=9;j++)" not in source, "Parallel global route bundles must not return"


def test_splash_reference_telemetry_and_typography_are_part_of_acceptance():
    source = _source()
    contract = _contract()
    missing_telemetry = _missing(source, ["top-agent-node","activity-bars","governance-trend","integrity-ring"])
    assert not missing_telemetry, f"Reference telemetry system is incomplete: {missing_telemetry}"
    typography = contract["typography"]
    assert typography["titles_use_display_font"] is True
    assert typography["status_uses_mono"] is True
    assert typography["arabic_body_rtl"] is True
    assert typography["arabic_body_not_mono"] is True
    assert "font:8px var(--mono)" in source or "font:7px var(--mono)" in source


def test_splash_reference_reduced_motion_must_remain_a_complete_static_board():
    source = _source()
    accessibility = _contract()["accessibility"]
    assert accessibility["reduced_motion"] is True
    assert accessibility["keyboard_focusable_modules"] is True
    assert accessibility["pointer_route_interaction_required"] is False
    assert accessibility["all_content_visible_in_desktop_stage"] is True
    required = [
        "@media(prefers-reduced-motion:reduce)", ".pulse{display:none}",
        'tabindex="0"', "requestAnimationFrame", "reduceMotion.addEventListener?.('change',rebuild)",
    ]
    missing = _missing(source, required)
    assert not missing, f"Reduced-motion/keyboard reference gate incomplete: {missing}"
    forbidden = ["focusRoute", "addEventListener('focus'", "addEventListener('blur'", "mouseenter", "mouseleave"]
    present = [marker for marker in forbidden if marker in source]
    assert not present, f"Pointer/focus-driven route behavior must stay disabled: {present}"
