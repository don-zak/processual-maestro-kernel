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
        "function ambient(",
        "function rebuild()",
        "function animate(now)",
        "getTotalLength",
        "getPointAtLength",
        "requestAnimationFrame",
    ]
    forbidden = [
        'id="bg-canvas"',
        "class Particle",
        "const COUNT = 80",
        "drawParticles()",
    ]
    missing = [marker for marker in required if marker not in source]
    legacy = [marker for marker in forbidden if marker in source]
    assert not missing, f"Missing reference living-board markers: {missing}"
    assert not legacy, f"Legacy starfield markers remain in production splash: {legacy}"


def test_production_splash_exposes_all_reference_modules_and_execution_node():
    source = _source()
    required = [
        'id="governance"',
        'id="supervision"',
        'id="calibration"',
        'id="orchestration"',
        'id="routing"',
        'id="policy"',
        'id="feedback"',
        'id="control"',
        'id="execution"',
        'data-key="governance"',
        'data-key="supervision"',
        'data-key="calibration"',
        'data-key="orchestration"',
        'data-key="routing"',
        'data-key="policy"',
        'data-key="feedback"',
        'data-key="control"',
        "GOVERNANCE",
        "SUPERVISION",
        "CALIBRATION",
        "ORCHESTRATION",
        "ROUTING",
        "POLICY ENGINE",
        "FEEDBACK LOOP",
        "CONTROL GATES",
        "EXECUTION",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing reference governance/control surface markers: {missing}"


def test_production_splash_preserves_real_entry_card_and_descent_gate_contract():
    source = _source()
    required = [
        '<div class="m">MAESTRO<span>.</span></div>',
        '<div class="s">PROCESSUAL KERNEL</div>',
        "API Server",
        "Database",
        "Cache",
        "Kernel",
        "All systems operational.",
        "Enter Maestro",
        "maestro_descent_gate_seen",
        "maestro_descent_gate_seen_at",
        "sessionStorage.setItem",
        "window.location.href = '/login'",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Production entry-card contract changed unexpectedly: {missing}"


def test_production_splash_routes_are_live_geometry_bound_and_interactive():
    source = _source()
    required = [
        "const w=board.clientWidth,h=board.clientHeight,c=rr(core)",
        "const n=rr(node),a=edge(c,n),b=node.id==='execution'?edge(n,c):connectorPoint(node)",
        "function connectorPoint(node)",
        "node.querySelector('.connector-pad')",
        "function pcb(",
        "function focusRoute(key)",
        "classList.toggle('active'",
        "classList.toggle('dim'",
        "mouseenter",
        "mouseleave",
        "focus",
        "blur",
        "addEventListener('resize'",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Reference routes are not fully connector-bound/interactive: {missing}"


def test_production_splash_uses_dense_reference_pcb_buses():
    source = _source()
    required = [
        "for(let j=-6;j<=6;j++)",
        "klass=j===0?'trace primary-bus main':Math.abs(j)<=3?'trace secondary-bus fine':'trace tertiary-bus ghost'",
        "for(let i=0;i<24;i++)",
        "for(let i=0;i<18;i++)",
        "for(let i=0;i<16;i++)",
        "function addBranches(",
        "[.24,.48,.72].forEach",
        "p3=E('circle'",
        "g.append(p1,p2,p3)",
        "primary-bus",
        "secondary-bus",
        "tertiary-bus",
        "via-node",
        "connector-pad",
        "top-agent-node",
        "bottom-execution-bus",
        "activity-bars",
        "governance-trend",
        "integrity-ring",
        "pin-side",
        "pin-top",
        "pin-bottom",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Dense live PCB choreography markers missing: {missing}"


def test_production_splash_keeps_reference_stage_scaling_and_reduced_motion_guards():
    source = _source()
    required = [
        "--stage-width:1440",
        "--stage-height:1080",
        "const fit_rule='contain'",
        "function fitStage()",
        "scale = Math.min(viewportWidth / 1440,viewportHeight / 1080)",
        "stage.style.transform=`scale(${scale})`",
        "addEventListener('resize',fitStage",
        "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',rebuild)",
        ".pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing 4:3 stage-scaling/reduced-motion protections: {missing}"
