from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
BOARD = STATIC / "splash_reference_board.svg"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def _board() -> str:
    return BOARD.read_text(encoding="utf-8")


def test_production_splash_uses_authored_svg_dom_hybrid_board():
    source = _source()
    required = [
        'id="pcb-reference"', 'src="./splash_reference_board.svg"', 'id="signal-svg"',
        'class="maestro-reference-stage"', "authoredSignalMap", "function registerSignal(",
        "function rebuildSignals()", "function animate(now)", "getTotalLength", "getPointAtLength",
        "requestAnimationFrame",
    ]
    forbidden = ["function pcb(", "function drawSideFabric(", "function regionalFabric(", "class Particle"]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_authored_reference_board_is_dense_layered_asymmetric_and_breathable():
    board = _board()
    required = [
        'viewBox="0 0 1672 941"', 'id="grid"', 'id="dotsC"', 'id="dotsA"', 'id="dotsV"',
        'id="glow"', 'id="terminalGlow"', 'stroke="#36bfff"', 'stroke="#e59a20"',
        'stroke="#23d8c8"', 'stroke="#c16fff"', '<ellipse cx="836" cy="452"',
        'sculpted module frame rails', 'balanced density envelope / visual breathing corridors',
        'long ambient branches that intentionally do not terminate at cards',
        'asymmetric right-side ambient fabric: intentionally not mirrored',
        'central-origin surface merge network', 'asymmetric right merge fabric',
        'organic micro-topology islands',
        'reference-flowing secondary branches with terminal dead-end nodes',
        'explicit dead-end flow branches: tapered spread, no card termination',
        'core rim integration: nested processor rails and pin landing geometry',
        'crown breakout with scattered hotspots; top rings deliberately removed',
        'crown side-slip dead ends',
        'execution radial fabric and bottom telemetry backplane',
        'lower dead-end fanout',
        'explicit wide-spread luminous via network / dense page-wide node matrices',
        'terminal beacons: upper crown + side dead ends + lower execution dead ends',
        'scattered passive micro-vias remain subordinate to route terminal hierarchy',
        'pin landing nodes',
    ]
    assert not [m for m in required if m not in board]
    assert 'ring via clusters' not in board
    assert board.count("<path") >= 100
    assert board.count("<circle") >= 80


def test_production_splash_is_full_landing_page():
    source = _source()
    required = [
        'class="site-header"', 'class="brand"', 'class="nav"', "PLATFORM⌄", "SOLUTIONS⌄",
        "RESOURCES⌄", "ABOUT⌄", "DOCS", "SYSTEM STATUS", "ALL SYSTEMS OPERATIONAL",
        'class="signin" href="/login"', 'class="telemetry-strip"', "SYSTEM METRICS",
        "THROUGHPUT", "LATENCY (P95)", "QUEUE DEPTH", "SYSTEM HEALTH",
        'class="site-footer"', "Privacy Policy", "Terms of Service", "Security", "© 2026 MAESTRO",
    ]
    assert not [m for m in required if m not in source]


def test_production_splash_exposes_all_reference_modules_and_execution():
    source = _source()
    required = [
        'id="governance"', 'id="supervision"', 'id="calibration"', 'id="orchestration"',
        'id="routing"', 'id="policy"', 'id="feedback"', 'id="control"', 'id="execution"',
        "GOVERNANCE", "SUPERVISION", "CALIBRATION", "ORCHESTRATION", "ROUTING",
        "POLICY ENGINE", "FEEDBACK LOOP", "CONTROL GATES", "EXECUTION", "connector-pad",
    ]
    assert not [m for m in required if m not in source]


def test_reference_modules_are_moved_outward_to_open_pcb_fabric_space():
    source = _source()
    required = [
        "#governance{left:78px;top:91px}", "#supervision{left:78px;top:268px}",
        "#calibration{left:78px;top:447px}", "#orchestration{left:78px;top:626px}",
        "#routing{right:78px;top:91px}", "#policy{right:78px;top:268px}",
        "#feedback{right:78px;top:447px}", "#control{right:78px;top:626px}",
        "left:642px;top:248px;width:388px;height:390px",
    ]
    assert not [m for m in required if m not in source]


def test_side_modules_are_embedded_and_visually_reduced():
    source = _source()
    required = [
        "transform:scale(.88)", "transform-origin:100% 50%", "transform-origin:0 50%",
        "/* embedded segmented reference card rails */",
        "background:linear-gradient(145deg,rgba(3,14,26,.58),rgba(2,9,18,.46))",
        "backdrop-filter:blur(5px)", "0 1px 3px rgba(0,0,0,.18)",
    ]
    assert not [m for m in required if m not in source]


def test_core_is_elevated_and_processor_teeth_are_slim_route_colored():
    source = _source()
    required = [
        "/* elevated central processor */", "transform:scale(1.045)",
        "filter:drop-shadow(0 16px 20px rgba(0,0,0,.34))",
        "/* slim route-colored processor teeth */", "width:4px", "height:4px",
        "linear-gradient(180deg,#21c9ff 0 24%,#22dfcd 24% 49%,#a7d67b 49% 74%,#c16fff 74% 100%)",
        "linear-gradient(180deg,#f1a21d 0 49%,#23d8c8 49% 75%,#c16fff 75% 100%)",
        "linear-gradient(90deg,#20c7ff 0 24%,#1ee0cf 24% 44%,#33cfff 44% 50%,#f0a21f 50% 80%,#ffc24d 80% 100%)",
        "linear-gradient(90deg,#20c7ff 0 22%,#23d8c8 22% 34%,#c16fff 34% 48%,#36bfff 48% 57%,#f0a21f 57% 72%,#c16fff 72% 100%)",
    ]
    assert not [m for m in required if m not in source]


def test_visual_trace_density_is_selectively_reduced_without_removing_live_semantics():
    source = _source()
    required = [
        "/* selective trace pruning veil */",
        "#pcb-reference{position:absolute;inset:0;width:1672px;height:941px;z-index:1;pointer-events:none;user-select:none;opacity:.88}",
        ".signal-base{stroke-width:.95;opacity:.64", ".signal-wake{stroke-width:2.3;opacity:.065",
        "p1=E('circle',{r:'2.4'", "p2=E('circle',{r:'1.5'", "p3=E('circle',{r:'1.0'",
    ]
    assert not [m for m in required if m not in source]


def test_authored_board_has_actual_pruning_vivid_routes_and_flowing_terminal_hierarchy():
    board = _board()
    required = [
        'aria-label="Maestro authored PCB reference fabric v9 flowing terminals"',
        '<g stroke="#36bfff" stroke-opacity=".16" stroke-width=".62">',
        '<g stroke="#e59a20" stroke-opacity=".17" stroke-width=".64">',
        '<g stroke="#36bfff" stroke-opacity=".91" stroke-width="1.16" filter="url(#glowC)">',
        '<g stroke="#e59a20" stroke-opacity=".93" stroke-width="1.18" filter="url(#glowA)">',
        '<g stroke="#23d8c8" stroke-opacity=".83" stroke-width="1.04" filter="url(#glow)">',
        '<g stroke="#c16fff" stroke-opacity=".86" stroke-width="1.05" filter="url(#glow)">',
        'id="terminal-beacons"', 'filter="url(#terminalGlow)"',
        'reference-flowing secondary branches with terminal dead-end nodes',
        'explicit dead-end flow branches: tapered spread, no card termination',
        'lower dead-end fanout', 'crown side-slip dead ends',
    ]
    assert not [m for m in required if m not in board]
    assert board.count('stroke-opacity=".16"') >= 1
    assert board.count('stroke-opacity=".17"') >= 1
    assert board.count('stroke-opacity=".91"') >= 1
    assert board.count('stroke-opacity=".93"') >= 1
    # Terminal nodes must exist at upper, side and lower dead-end endpoints.
    for marker in [
        '<circle cx="672" cy="102" r="2.7" fill="#36bfff"/>',
        '<circle cx="386" cy="331" r="2.4" fill="#36bfff"/>',
        '<circle cx="1287" cy="327" r="2.4" fill="#e59a20"/>',
        '<circle cx="676" cy="743" r="2.4" fill="#36bfff"/>',
        '<circle cx="1029" cy="789" r="2.3" fill="#c16fff"/>',
    ]:
        assert marker in board


def test_cover_fit_uses_adaptive_safe_bands_for_chrome_and_telemetry():
    source = _source()
    required = [
        "/* adaptive safe bands keep reference chrome visible under cover-fit */",
        "--header-drop:0px", "--footer-lift:0px", "--telemetry-lift:0px", "--safe-x:0px",
        "const visibleWorldWidth=viewportWidth/scale,visibleWorldHeight=viewportHeight/scale",
        "const cropX=Math.max(0,(1672-visibleWorldWidth)/2),cropY=Math.max(0,(941-visibleWorldHeight)/2)",
        "stage.style.setProperty('--safe-x'", "stage.style.setProperty('--header-drop'",
        "stage.style.setProperty('--footer-lift'", "stage.style.setProperty('--telemetry-lift'",
    ]
    assert not [m for m in required if m not in source]


def test_entry_card_and_descent_gate_contract_remain_intact():
    source = _source()
    required = [
        '<div class="m">MAESTRO<span>.</span></div>', "Agent Governance, Calibration &amp;",
        "Supervision Orchestration Platform", "API Server", "Database", "Cache", "Kernel",
        "All systems operational.", "Enter Maestro", "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at", "sessionStorage.setItem", "window.location.href = '/login'",
        "background:rgba(22,29,42,.68)",
    ]
    assert not [m for m in required if m not in source]


def test_signal_layer_is_semantic_autonomous_and_not_mirrored():
    source = _source()
    required = [
        "signalDirection", "governance:'outbound'", "supervision:'inbound'",
        "calibration:'bidirectional'", "control:'roundtrip'", "execution:'downstream'",
        "semanticT(", "requestAnimationFrame(animate)", "signal-wake", "node-bloom",
        "destination-ack", "p3=E('circle'", "M1276 162 H1214 L1188 146",
    ]
    forbidden = ["mouseenter", "mouseleave", "focusRoute(", "classList.toggle('dim'"]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_reference_cover_and_reduced_motion_guards_remain():
    source = _source()
    required = [
        "--stage-width:1672", "--stage-height:941", "const fit_rule='reference-cover-1672x941'",
        "function fitStage()", "Math.max(viewportWidth/1672,viewportHeight/941)", "worldWidth=1672",
        "stage.style.transform=`translate(-50%,-50%) scale(${scale})`", "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches", "reduceMotion.addEventListener?.('change',rebuildSignals)", ".pulse{display:none}",
    ]
    assert not [m for m in required if m not in source]
