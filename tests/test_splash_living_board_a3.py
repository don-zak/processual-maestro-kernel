from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "processual_api" / "static" / "splash.html"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def test_production_splash_uses_reference_living_board_not_legacy_starfield():
    source = _source()
    required = [
        'id="board"', 'id="trace-svg"', 'class="maestro-reference-stage"',
        "function drawAmbientBoard(", "function drawModuleFrames(", "function drawCoreBreakout(",
        "function drawUpperFabric(", "function drawExecutionFabric(", "function drawCrossFabric(c)",
        "function drawBackplaneFabric(c)", "function rings(", "function rebuild()", "function animate(now)",
        "getTotalLength", "getPointAtLength", "requestAnimationFrame",
    ]
    forbidden = ['id="bg-canvas"', "class Particle", "const COUNT = 80", "drawParticles()"]
    missing = [marker for marker in required if marker not in source]
    legacy = [marker for marker in forbidden if marker in source]
    assert not missing, f"Missing SVG-first living-board markers: {missing}"
    assert not legacy, f"Legacy starfield markers remain in production splash: {legacy}"


def test_production_splash_is_a_full_landing_page_not_only_a_splash_card():
    source = _source()
    required = [
        'class="site-header"', 'class="brand"', 'class="nav"', "PLATFORM⌄", "SOLUTIONS⌄",
        "RESOURCES⌄", "ABOUT⌄", "DOCS", "SYSTEM STATUS", "ALL SYSTEMS OPERATIONAL",
        'class="signin" href="/login"', 'class="telemetry-strip"', "SYSTEM METRICS",
        "THROUGHPUT", "LATENCY (P95)", "QUEUE DEPTH", "SYSTEM HEALTH",
        'class="site-footer"', "Privacy Policy", "Terms of Service", "Security", "© 2026 MAESTRO",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Full landing-page shell is incomplete: {missing}"


def test_production_splash_exposes_all_reference_modules_and_execution_node():
    source = _source()
    required = [
        'id="governance"', 'id="supervision"', 'id="calibration"', 'id="orchestration"',
        'id="routing"', 'id="policy"', 'id="feedback"', 'id="control"', 'id="execution"',
        'data-key="governance"', 'data-key="supervision"', 'data-key="calibration"',
        'data-key="orchestration"', 'data-key="routing"', 'data-key="policy"',
        'data-key="feedback"', 'data-key="control"', "GOVERNANCE", "SUPERVISION", "CALIBRATION",
        "ORCHESTRATION", "ROUTING", "POLICY ENGINE", "FEEDBACK LOOP", "CONTROL GATES", "EXECUTION",
        "edge-rail",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing reference governance/control surface markers: {missing}"


def test_production_splash_preserves_entry_and_descent_gate_contract():
    source = _source()
    required = [
        '<div class="m">MAESTRO<span>.</span></div>', "Agent Governance, Calibration &amp;",
        "Supervision Orchestration Platform", "API Server", "Database", "Cache", "Kernel",
        "All systems operational.", "Enter Maestro", "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at", "sessionStorage.setItem", "window.location.href = '/login'",
        "background:rgba(22,29,42,.68)",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Production entry-card contract changed unexpectedly: {missing}"


def test_production_splash_routes_use_regional_fabric_and_not_long_bridge_generator():
    source = _source()
    required = [
        "function connectorPoint(node)", "node.querySelector('.connector-pad')", "fabricProfiles",
        "function localFanout(", "function regionalFabric(", "function drawCrossFabric(c)",
        "function drawBackplaneFabric(c)", "function registerSignal(", "function animate(now)", "semanticT(",
        "requestAnimationFrame(animate)", "addEventListener('resize'",
    ]
    forbidden = [
        "function pcb(", "for(let j=-9;j<=9;j++)", "function drawSideFabric(", "function focusRoute(key)",
        "mouseenter", "mouseleave", "classList.toggle('active'", "classList.toggle('dim'",
    ]
    missing = [marker for marker in required if marker not in source]
    old_route_engine = [marker for marker in forbidden if marker in source]
    assert not missing, f"Regional authored routes incomplete: {missing}"
    assert not old_route_engine, f"Long-bridge/generic routing returned unexpectedly: {old_route_engine}"


def test_production_splash_uses_reference_pcb_density_and_topology():
    source = _source()
    required = [
        "function drawAmbientBoard(", "function drawCoreBreakout(", "function localFanout(",
        "function regionalFabric(", "function drawCrossFabric(c)", "function drawBackplaneFabric(c)",
        "function drawGovernanceFabric()", "function drawSupervisionFabric()", "function drawCalibrationFabric()",
        "function drawOrchestrationFabric()", "function drawRoutingFabric()", "function drawPolicyFabric()",
        "function drawFeedbackFabric()", "function drawControlFabric()", "function drawUpperFabric(",
        "function drawExecutionFabric(", "for(let i=0;i<132;i++)", "for(let i=0;i<92;i++)",
        "for(let i=0;i<44;i++)", "for(let i=0;i<48;i++)", "for(let i=0;i<38;i++)",
        "for(let i=0;i<32;i++", "for(let i=0;i<18;i++", ".trace.dormant", ".trace.support",
        ".trace.active", ".trace.hot", "via-node", "connector-pad", "node-bloom", "trace-wake",
        "p3=E('circle'", "g.append(p1,p2,p3)", "telemetry-strip", "pin-side", "pin-top", "pin-bottom",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Reference SVG PCB density/topology markers missing: {missing}"


def test_production_splash_uses_svg_module_frames_and_reference_geometry():
    source = _source()
    required = [
        "function framePath(r,side)", "function drawModuleFrames()", "data-frame",
        "fill:'rgba(4,12,23,.59)'", "stroke:color",
        ".module{--accent:var(--cyan-normal);position:absolute;width:318px;height:143px",
        ".icon::before,.icon::after", "width:84px;height:84px", "left:622px;top:260px;width:390px;height:384px",
        "#governance{left:136px;top:91px}", "#supervision{left:136px;top:268px}",
        "#calibration{left:136px;top:447px}", "#orchestration{left:136px;top:626px}",
        "#routing{right:136px;top:91px}", "#policy{right:136px;top:268px}",
        "#feedback{right:136px;top:447px}", "#control{right:136px;top:626px}",
    ]
    forbidden = [".module::before,.module::after", "clip-path:polygon(0 14%,4% 6%,15% 6%"]
    missing = [marker for marker in required if marker not in source]
    legacy = [marker for marker in forbidden if marker in source]
    assert not missing, f"Reference module/card geometry missing: {missing}"
    assert not legacy, f"Legacy CSS panel geometry returned unexpectedly: {legacy}"


def test_production_splash_keeps_reference_contain_and_reduced_motion_guards():
    source = _source()
    required = [
        "--stage-width:1672", "--stage-height:941", "const fit_rule='reference-contain-1672x941'",
        "function fitStage()", "const scale=Math.min(viewportWidth/1672,viewportHeight/941)",
        "worldWidth=1672", "stage.style.transform=`translate(-50%,-50%) scale(${scale})`",
        "addEventListener('resize',fitStage", "@media(prefers-reduced-motion:reduce)", "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',rebuild)", ".pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing reference-contain/reduced-motion protections: {missing}"
