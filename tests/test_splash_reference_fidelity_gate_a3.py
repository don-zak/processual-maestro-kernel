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
    assert contract["contract_version"] == "A3-splash-reference-v4"
    assert contract["score_total"] == 100
    assert contract["minimum_score"] >= 99
    assert sum(contract["scoring"].values()) == 100
    assert contract["reference_stage"]["width"] == 1672
    assert contract["reference_stage"]["height"] == 941
    assert contract["reference_stage"]["fit_rule"] == "reference-contain-1672x941"


def test_splash_core_entry_card_is_a_non_compensable_gate():
    source = _source()
    contract = _contract()["mandatory_core_contract"]
    missing_content = _missing(source, contract["preserve_card_markers"])
    missing_color = _missing(source, contract["preserve_color_markers"])
    assert contract["preserve_dark_card"] is True
    assert not missing_content, f"Central Maestro entry-card contract changed unexpectedly: {missing_content}"
    assert not missing_color, f"Central Maestro entry-card identity changed unexpectedly: {missing_color}"


def test_splash_reference_geometry_contract_is_machine_readable():
    contract = _contract()["logical_layout"]
    assert contract["core_bounds"] == {"x": 622, "y": 260, "w": 390, "h": 384, "tolerance_px": 18}
    assert contract["execution_center"] == {"x": 836, "y": 757, "tolerance_px": 24}
    assert set(contract["modules"]) == {
        "governance", "supervision", "calibration", "orchestration",
        "routing", "policy", "feedback", "control",
    }
    assert {module["side"] for module in contract["modules"].values()} == {"left", "right"}
    assert all(module["w"] == 318 for module in contract["modules"].values())
    assert all(module["h"] == 143 for module in contract["modules"].values())


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
            "secondary_cards_are_nodes_not_dashboard_cards","connector-pad","fabricProfiles",
        ], scoring["module_geometry_and_hierarchy"]),
        "pcb_density_and_connectivity": (contract["pcb"]["required_markers"], scoring["pcb_density_and_connectivity"]),
        "motion_semantics": (
            contract["motion"]["required_markers"] + [
                "governance:'outbound'","policy:'outbound'","routing:'outbound'",
                "supervision:'inbound'","feedback:'inbound'","calibration:'bidirectional'",
                "orchestration:'bidirectional'","control:'roundtrip'","execution:'downstream'",
            ], scoring["motion_semantics"]),
        "telemetry_and_depth": (["top-agent-node","telemetry-strip","SYSTEM METRICS","SYSTEM HEALTH"], scoring["telemetry_and_depth"]),
        "color_and_typography": (
            contract["color_system"]["background_layers"] + contract["color_system"]["cyan_levels"]
            + contract["color_system"]["amber_levels"] + ["direction:rtl","var(--display)","var(--mono)","Georgia"],
            scoring["color_and_typography"],
        ),
        "accessibility_and_responsiveness": ([
            "@media(prefers-reduced-motion:reduce)","tabindex=\"0\"","requestAnimationFrame",
            "addEventListener('resize'","fit_rule","worldWidth=1672",
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
        + " | ".join(details)
    )


def test_splash_motion_semantics_are_not_decorative_only():
    source = _source()
    motion = _contract()["motion"]
    assert motion["trace_wake_required"] is True
    assert motion["node_bloom_required"] is True
    assert motion["destination_ack_required"] is True
    assert motion["autonomous_motion_required"] is True
    assert motion["pointer_route_interaction_required"] is False
    missing = _missing(source, motion["required_markers"])
    assert not missing, f"Motion semantics incomplete: {missing}"
    forbidden = ["mouseenter", "mouseleave", "focusRoute(", "classList.toggle('dim'"]
    assert not [marker for marker in forbidden if marker in source]


def test_splash_reference_requires_regional_and_backplane_pcb_fabric_not_long_bridges():
    source = _source()
    pcb = _contract()["pcb"]
    assert pcb["regional_bus_required"] is True
    assert pcb["local_fanout_required"] is True
    assert pcb["cross_fabric_required"] is True
    assert pcb["backplane_fabric_required"] is True
    missing = _missing(source, pcb["required_markers"])
    assert not missing, f"Regional/backplane connector PCB topology is incomplete: {missing}"
    forbidden = ["function pcb(", "for(let j=-9;j<=9;j++)", "function drawSideFabric("]
    assert not [marker for marker in forbidden if marker in source]


def test_splash_reference_telemetry_and_typography_are_part_of_acceptance():
    source = _source()
    typography = _contract()["typography"]
    assert typography["titles_use_display_font"] is True
    assert typography["status_uses_mono"] is True
    assert typography["arabic_body_rtl"] is True
    assert typography["arabic_body_not_mono"] is True
    assert typography["core_maestro_uses_serif"] is True
    assert "telemetry-strip" in source
    assert "Georgia" in source


def test_splash_reference_reduced_motion_must_remain_a_complete_static_board():
    source = _source()
    accessibility = _contract()["accessibility"]
    assert accessibility["reduced_motion"] is True
    assert accessibility["keyboard_focusable_modules"] is True
    required = ["@media(prefers-reduced-motion:reduce)", ".pulse{display:none}", 'tabindex="0"', "requestAnimationFrame"]
    assert not _missing(source, required)
