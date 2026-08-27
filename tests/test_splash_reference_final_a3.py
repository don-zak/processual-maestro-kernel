from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "processual_api" / "static"
SPLASH = STATIC / "splash.html"
ROUTE_LAYERS = [
    "splash_routes_cyan.svg",
    "splash_routes_teal.svg",
    "splash_routes_lime.svg",
    "splash_routes_amber.svg",
    "splash_routes_violet.svg",
]


def test_splash_uses_reference_coordinate_system_and_all_route_families() -> None:
    html = SPLASH.read_text(encoding="utf-8")

    assert "1672px" in html
    assert "941px" in html
    assert "left:608px" in html
    assert "top:224px" in html
    assert "width:433px" in html
    assert "height:408px" in html

    for filename in ROUTE_LAYERS:
        assert f'/console/{filename}' in html
        route = (STATIC / filename).read_text(encoding="utf-8")
        assert 'viewBox="0 0 1672 941"' in route
        assert "<path" in route


def test_splash_contains_eight_side_cards_and_reference_depth_hierarchy() -> None:
    html = SPLASH.read_text(encoding="utf-8")

    assert html.count('<section class="card ') == 8
    assert "border-radius:12px" in html
    assert "box-shadow:0 30px 45px" in html
    assert "core-shadow" in html
    assert "execution" in html


def test_splash_preserves_required_navigation_and_reduced_motion() -> None:
    html = SPLASH.read_text(encoding="utf-8")

    assert 'href="/login"' in html
    assert 'href="/register"' in html
    assert 'href="/pricing"' in html
    assert 'href="/docs"' in html
    assert "prefers-reduced-motion:reduce" in html


def test_splash_does_not_restore_procedural_route_generation() -> None:
    html = SPLASH.read_text(encoding="utf-8")

    forbidden = (
        "Math.random",
        "randomRoute",
        "generateRoute",
        "routeBuilder",
        "synthetic-route",
        "const routes={}",
    )
    for token in forbidden:
        assert token not in html
