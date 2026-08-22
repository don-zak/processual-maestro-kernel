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
        "function microField(",
        "function drawModuleFrames(",
        "function drawChipFanout(",
        "function crown(",
        "function executionBay(",
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
        'class="site-header"',
        'class="brand"',
        'class="nav"',
        "PLATFORM⌄",
        "SOLUTIONS⌄",
        "RESOURCES⌄",
        "ABOUT⌄",
        "DOCS",
        "SYSTEM STATUS",
        "ALL SYSTEMS OPERATIONAL",
        'class="signin" href="/login"',
        'class="telemetry-strip"',
        "SYSTEM METRICS",
        "THROUGHPUT",
        "TASK SUCCESS RATE",
        "LATENCY",
        "QUEUE DEPTH",
        "SYSTEM HEALTH",
        'class="site-footer"',
        "Privacy Policy",
        "Terms of Service",
        "Security",
        "© 2026 MAESTRO",
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
        'data-key="feedback"', 'data-key="control"',
        "GOVERNANCE", "SUPERVISION", "CALIBRATION", "ORCHESTRATION", "ROUTING",
        "POLICY ENGINE", "FEEDBACK LOOP", "CONTROL GATES", "EXECUTION",
        "edge-rail",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing reference governance/control surface markers: {missing}"


def test_production_splash_preserves_real_entry_card_and_descent_gate_contract():
    source = _source()
    required = [
        '<div class="m">MAESTRO<span>.</span></div>',
        '<div class="s">PROCESSUAL KERNEL</div>',
        "API Server", "Database", "Cache", "Kernel", "All systems operational.",
        "Enter Maestro", "maestro_descent_gate_seen", "maestro_descent_gate_seen_at",
        "sessionStorage.setItem", "window.location.href = '/login'",
        "background:rgba(22,29,42,.68)",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Production entry-card contract changed unexpectedly: {missing}"


def test_production_splash_routes_are_geometry_bound_and_self_animated_without_hover_dependency():
    source = _source()
    required = [
        "const n=rr(node),a=edge(c,n),b=node.id==='execution'?edge(n,c):connectorPoint(node)",
        "function connectorPoint(node)",
        "node.querySelector('.connector-pad')",
        "function pcb(",
        "function animate(now)",
        "semanticT(",
        "requestAnimationFrame(animate)",
        "addEventListener('resize'",
    ]
    forbidden = [
        "function focusRoute(key)",
        "mouseenter",
        "mouseleave",
        "classList.toggle('active'",
        "classList.toggle('dim'",
    ]
    missing = [marker for marker in required if marker not in source]
    hover_deps = [marker for marker in forbidden if marker in source]
    assert not missing, f"Reference routes are not fully connector-bound/self-animated: {missing}"
    assert not hover_deps, f"Hover-dependent routing returned unexpectedly: {hover_deps}"


def test_production_splash_uses_svg_first_reference_pcb_density_and_topology():
    source = _source()
    required = [
        "for(let j=-9;j<=9;j++)",
        "klass=j===0?'trace primary-bus main':Math.abs(j)<=4?'trace secondary-bus fine':'trace tertiary-bus ghost'",
        "for(let i=0;i<76;i++)",
        "for(let i=0;i<48;i++)",
        "for(let i=0;i<26;i++)",
        "for(let i=0;i<30;i++)",
        "for(let i=0;i<24;i++)",
        "[.1,.22,.34,.46,.58,.7,.82,.92].forEach",
        "function microField(",
        "function drawModuleFrames(",
        "function drawChipFanout(",
        "function crown(",
        "function executionBay(",
        "function rings(",
        "bottom-execution-bus",
        "trace micro",
        "primary-bus",
        "secondary-bus",
        "tertiary-bus",
        "via-node",
        "connector-pad",
        "node-bloom",
        "trace-wake",
        "p3=E('circle'",
        "g.append(p1,p2,p3)",
        "telemetry-strip",
        "pin-side",
        "pin-top",
        "pin-bottom",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"SVG-first PCB density/topology markers missing: {missing}"


def test_production_splash_uses_svg_module_frames_instead_of_css_card_panels():
    source = _source()
    required = [
        "function framePath(r,side)",
        "function drawModuleFrames()",
        "data-frame",
        "fill:'rgba(4,12,23,.56)'",
        "stroke:color",
        ".module{--accent:var(--cyan-normal);position:absolute;width:350px;height:138px",
        ".icon::before,.icon::after",
        "width:78px;height:78px",
        "width:470px;height:420px",
        "edge-rail",
    ]
    forbidden = [
        ".module::before,.module::after",
        "clip-path:polygon(0 14%,4% 6%,15% 6%",
    ]
    missing = [marker for marker in required if marker not in source]
    css_card_frames = [marker for marker in forbidden if marker in source]
    assert not missing, f"SVG-first module/card geometry missing: {missing}"
    assert not css_card_frames, f"Legacy CSS card-frame geometry returned unexpectedly: {css_card_frames}"


def test_production_splash_keeps_full_bleed_stage_and_reduced_motion_guards():
    source = _source()
    required = [
        "--stage-width:1440", "--stage-height:1080", "const fit_rule='full-bleed-fluid-width'",
        "function fitStage()", "worldWidth=Math.max(1440,viewportWidth / scale)",
        "stage.style.width=`${worldWidth}px`",
        "stage.style.transform=`translate(${offsetX}px,${offsetY}px) scale(${scale})`",
        "addEventListener('resize',fitStage", "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches", "reduceMotion.addEventListener?.('change',rebuild)", ".pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing full-bleed stage/reduced-motion protections: {missing}"
