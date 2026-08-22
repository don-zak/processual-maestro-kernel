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


def test_authored_reference_board_is_dense_and_layered():
    board = _board()
    required = [
        'viewBox="0 0 1672 941"', 'id="grid"', 'id="glowC"', 'id="glowA"',
        'stroke="#36bfff"', 'stroke="#e59a20"', 'stroke="#23d8c8"', 'stroke="#c16fff"',
        '<ellipse cx="836" cy="452"', '<circle cx="456" cy="165"',
    ]
    assert not [m for m in required if m not in board]
    assert board.count("<path") >= 70
    assert board.count("<circle") >= 12


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


def test_signal_layer_is_semantic_and_autonomous():
    source = _source()
    required = [
        "signalDirection", "governance:'outbound'", "supervision:'inbound'",
        "calibration:'bidirectional'", "control:'roundtrip'", "execution:'downstream'",
        "semanticT(", "requestAnimationFrame(animate)", "signal-wake", "node-bloom",
        "destination-ack", "p3=E('circle'",
    ]
    forbidden = ["mouseenter", "mouseleave", "focusRoute(", "classList.toggle('dim'"]
    assert not [m for m in required if m not in source]
    assert not [m for m in forbidden if m in source]


def test_reference_contain_and_reduced_motion_guards_remain():
    source = _source()
    required = [
        "--stage-width:1672", "--stage-height:941", "const fit_rule='reference-contain-1672x941'",
        "function fitStage()", "Math.min(viewportWidth/1672,viewportHeight/941)", "worldWidth=1672",
        "stage.style.transform=`translate(-50%,-50%) scale(${scale})`", "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches", "reduceMotion.addEventListener?.('change',rebuildSignals)", ".pulse{display:none}",
    ]
    assert not [m for m in required if m not in source]
