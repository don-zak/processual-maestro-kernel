from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "processual_api" / "static" / "splash.html"


def _source() -> str:
    return SPLASH.read_text(encoding="utf-8")


def test_production_splash_uses_living_maestro_board_not_legacy_starfield():
    source = _source()
    required = [
        'id="maestro-board"',
        'id="signal-svg"',
        "function ambient(",
        "function build()",
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
    assert not missing, f"Missing living-board markers: {missing}"
    assert not legacy, f"Legacy starfield markers remain in production splash: {legacy}"


def test_production_splash_exposes_all_governance_control_modules_and_execution_node():
    source = _source()
    required = [
        'data-module="governance"',
        'data-module="supervision"',
        'data-module="calibration"',
        'data-module="orchestration"',
        'data-module="routing"',
        'data-module="policy"',
        'data-module="feedback"',
        'data-module="control"',
        'id="execution-zone"',
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
    assert not missing, f"Missing governance/control surface markers: {missing}"


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
        "const cr=rr(card)",
        "const mr=rr(m)",
        "edgeAnchor(cr,mc)",
        "edgeAnchor(mr,cc)",
        "function focusRoute(key)",
        "classList.toggle('active'",
        "classList.toggle('dim'",
        "mouseenter",
        "mouseleave",
        "focus",
        "blur",
        "window.addEventListener('resize'",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Living routes are not fully geometry-bound/interactive: {missing}"


def test_production_splash_keeps_responsive_and_reduced_motion_guards():
    source = _source()
    required = [
        "@media(max-width:1220px)",
        "@media(max-width:900px)",
        "@media(max-width:560px)",
        "@media(prefers-reduced-motion:reduce)",
        "reduceMotion.matches",
        "reduceMotion.addEventListener?.('change',build)",
        ".signal-pulse{display:none}",
    ]
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing responsive/reduced-motion protections: {missing}"
