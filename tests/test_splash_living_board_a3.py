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
        "const n=rr(node),a=edge(c,n),b=edge(n,c)",
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
    assert not missing, f"Reference routes are not fully geometry-bound/interactive: {missing}"


def test_production_splash_uses_dense_reference_pcb_buses():
    source = _source()
    required = [
        "for(let j=-6;j<=6;j++)",
        "class:j===0?'trace main':Math.abs(j)<=3?'trace fine':'trace ghost'",
        "for(let i=0;i<24;i++)",
        "for(let i=0;i<18;i++)",
        "for(let i=0;i<16;i++)",
        "function addBranches(",
        "[.24,.48,.72].forEach",
        "const p3=E('circle'",
        "pin-side",
        "pin-top",
        "pin-bottom",
        "agent-matrix",
        "hud-left",
        "hud-right",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Dense live PCB choreography markers missing: {missing}"


def test_production_splash_keeps_responsive_and_reduced_motion_guards():
    source = _source()
    required = [
        "@media(max-width:1250px)",
        "@media(max-width:980px)",
        "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',rebuild)",
        ".pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing responsive/reduced-motion protections: {missing}"
