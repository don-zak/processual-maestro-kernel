from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "processual_api" / "static" / "splash.html"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def test_production_splash_uses_reference_living_board_not_legacy_starfield():
    source = _source()
    required = [
        'id="board"',
        'id="trace-svg"',
        'class="maestro-reference-stage"',
        "function drawAmbientBoard(",
        "function drawModuleFrames(",
        "function drawCoreBreakout(",
        "function drawUpperFabric(",
        "function drawExecutionFabric(",
        "function rings(",
        "function rebuild()",
        "function animate(now)",
        "getTotalLength",
        "getPointAtLength",
        "requestAnimationFrame",
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
        "THROUGHPUT", "TASK SUCCESS RATE", "LATENCY (P95)", "QUEUE DEPTH", "SYSTEM HEALTH",
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


def test_production_splash_preserves_real_entry_card_and_descent_gate_contract():
    source = _source()
    required = [
        '<div class="m">MAESTRO<span>.</span></div>', '<div class="s">PROCESSUAL KERNEL</div>',
        "API Server", "Database", "Cache", "Kernel", "All systems operational.", "Enter Maestro",
        "maestro_descent_gate_seen", "maestro_descent_gate_seen_at", "sessionStorage.setItem",
        "window.location.href = '/login'", "background:rgba(22,29,42,.68)",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Production entry-card contract changed unexpectedly: {missing}"


def test_production_splash_routes_are_authored_and_self_animated_without_hover_dependency():
    source = _source()
    required = [
        "function connectorPoint(node)", "node.querySelector('.connector-pad')", "function drawSideFabric(",
        "function registerSignal(", "function animate(now)", "semanticT(", "requestAnimationFrame(animate)",
        "addEventListener('resize'",
    ]
    forbidden = [
        "function pcb(", "for(let j=-9;j<=9;j++)", "function focusRoute(key)", "mouseenter", "mouseleave",
        "classList.toggle('active'", "classList.toggle('dim'",
    ]
    missing = [marker for marker in required if marker not in source]
    old_route_engine = [marker for marker in forbidden if marker in source]
    assert not missing, f"Authored routes are not fully connector-bound/self-animated: {missing}"
    assert not old_route_engine, f"Generic or hover-dependent routing returned unexpectedly: {old_route_engine}"


def test_production_splash_uses_authored_reference_pcb_density_and_topology():
    source = _source()
    required = [
        "function drawAmbientBoard(", "function drawCoreBreakout(", "function drawSideFabric(",
        "function drawGovernanceFabric()", "function drawSupervisionFabric()", "function drawCalibrationFabric()",
        "function drawOrchestrationFabric()", "function drawRoutingFabric()", "function drawPolicyFabric()",
        "function drawFeedbackFabric()", "function drawControlFabric()", "function drawUpperFabric(",
        "function drawExecutionFabric(", "for(let i=0;i<44;i++)", "for(let i=0;i<36;i++)",
        "for(let i=0;i<28;i++)", "for(let i=0;i<34;i++)", "for(let i=0;i<26;i++)",
        "for(let i=0;i<14;i++)", "for(let i=0;i<8;i++)", "trace dormant", "trace support",
        "trace active", "trace hot", "via-node", "connector-pad", "node-bloom", "trace-wake",
        "p3=E('circle'", "g.append(p1,p2,p3)", "telemetry-strip", "pin-side", "pin-top", "pin-bottom",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Authored SVG PCB density/topology markers missing: {missing}"


def test_production_splash_uses_svg_module_frames_instead_of_css_card_panels():
    source = _source()
    required = [
        "function framePath(r,side)", "function drawModuleFrames()", "data-frame", "fill:'rgba(4,12,23,.56)'",
        "stroke:color", ".module{--accent:var(--cyan-normal);position:absolute;width:315px;height:145px",
        ".icon::before,.icon::after", "width:80px;height:80px", "width:480px;height:440px", "edge-rail",
    ]
    forbidden = [".module::before,.module::after", "clip-path:polygon(0 14%,4% 6%,15% 6%"]
    missing = [marker for marker in required if marker not in source]
    css_card_frames = [marker for marker in forbidden if marker in source]
    assert not missing, f"SVG-first module/card geometry missing: {missing}"
    assert not css_card_frames, f"Legacy CSS card-frame geometry returned unexpectedly: {css_card_frames}"


def test_production_splash_keeps_reference_geometry_full_bleed_and_reduced_motion_guards():
    source = _source()
    required = [
        "--stage-width:1440", "--stage-height:1080", "const fit_rule='full-bleed-fluid-width'", "function fitStage()",
        "worldWidth=Math.max(1440,viewportWidth/scale)", "stage.style.width=`${worldWidth}px`",
        "stage.style.transform=`translate(${offsetX}px,${offsetY}px) scale(${scale})`", "top:295px;width:480px;height:440px",
        "#governance{left:35px;top:110px}", "#supervision{left:35px;top:335px}",
        "#calibration{left:35px;top:555px}", "#orchestration{left:35px;top:775px}",
        "#routing{right:35px;top:110px}", "#policy{right:35px;top:335px}",
        "#feedback{right:35px;top:555px}", "#control{right:35px;top:775px}",
        "addEventListener('resize',fitStage", "@media(prefers-reduced-motion:reduce)", "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',rebuild)", ".pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing reference geometry/full-bleed/reduced-motion protections: {missing}"
