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
    assert not missing, f"Missing near-reference living-board markers: {missing}"
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


def test_production_splash_uses_near_reference_pcb_density_and_topology():
    source = _source()
    required = [
        "for(let j=-9;j<=9;j++)",
        "klass=j===0?'trace primary-bus main':Math.abs(j)<=4?'trace secondary-bus fine':'trace tertiary-bus ghost'",
        "for(let i=0;i<52;i()" if False else "for(let i=0;i<52;i++)",
        "for(let i=0;i<34;i++)",
        "const count=30",
        "const count=24",
        "[.13,.26,.39,.52,.65,.78,.9].forEach",
        "function microField(",
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
        "activity-bars",
        "governance-trend",
        "integrity-ring",
        "pin-side",
        "pin-top",
        "pin-bottom",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Near-reference PCB density/topology markers missing: {missing}"


def test_production_splash_cards_use_open_reference_like_frames_and_hex_sockets():
    source = _source()
    required = [
        ".module::before,.module::after",
        "clip-path:polygon(0 14%,4% 6%,15% 6%,18% 0,88% 0,94% 6%,100% 6%,100% 86%,96% 94%,86% 94%,82% 100%,13% 100%,7% 94%,0 94%)",
        ".icon::before,.icon::after",
        "width:82px;height:82px",
        "width:390px;height:150px",
        "width:550px;height:500px",
        "edge-rail",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Reference-like open card/socket geometry missing: {missing}"


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
