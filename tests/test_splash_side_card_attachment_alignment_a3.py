from pathlib import Path
import re


STATIC = Path("processual_api/static")
SPLASH = STATIC / "splash.html"
ROUTE_FILES = tuple(STATIC / f"splash_routes_{family}.svg" for family in ("cyan", "teal", "lime", "amber", "violet"))


def _splash_html() -> str:
    return SPLASH.read_text(encoding="utf-8")


def _canonical_route_points() -> list[tuple[int, int]]:
    points: list[tuple[int, int]] = []
    for route_file in ROUTE_FILES:
        source = route_file.read_text(encoding="utf-8")
        for x, y in re.findall(r"[ML](-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", source):
            points.append((round(float(x)), round(float(y))))
    return points


def test_side_card_bounds_align_with_reference_attachment_zones() -> None:
    html = _splash_html()

    width_match = re.search(r"\.card\{[^}]*width:(\d+)px;[^}]*height:(\d+)px", html)
    left_match = re.search(
        r"\.card\.c1,\.card\.c2,\.card\.c3,\.card\.c4\{left:(\d+)px\}",
        html,
    )
    right_match = re.search(
        r"\.card\.r1,\.card\.r2,\.card\.r3,\.card\.r4\{right:(\d+)px\}",
        html,
    )

    assert width_match is not None
    assert left_match is not None
    assert right_match is not None

    stage_width = 1672
    card_width = int(width_match.group(1))
    card_height = int(width_match.group(2))
    left = int(left_match.group(1))
    right = int(right_match.group(1))

    assert (card_width, card_height) == (335, 140)
    assert left + card_width == 415
    assert stage_width - right - card_width == 1240

    expected_vertical_markers = [
        ".card.c1,.card.r1{top:90px}",
        ".card.c2,.card.r2{top:257px}",
        ".card.c3,.card.r3{top:426px}",
        ".card.c4,.card.r4{top:598px}",
    ]
    missing = [marker for marker in expected_vertical_markers if marker not in html]
    assert not missing, f"Missing reference vertical module bounds: {missing}"


def test_every_side_module_has_canonical_route_support_near_its_inner_edge() -> None:
    points = _canonical_route_points()
    assert points, "Canonical route SVGs must expose route coordinates"

    # Route geometry remains authoritative. This gate only proves that each visual
    # module occupies a reference zone with nearby canonical support; it does not
    # synthesize or extend a route into a card.
    module_zones = {
        "c1-governance": (415, 90, 230),
        "c2-supervision": (415, 257, 397),
        "c3-calibration": (415, 426, 566),
        "c4-orchestration": (415, 598, 738),
        "r1-routing": (1240, 90, 230),
        "r2-policy-engine": (1240, 257, 397),
        "r3-feedback-loop": (1240, 426, 566),
        "r4-control-gates": (1240, 598, 738),
    }

    horizontal_tolerance = 35
    vertical_tolerance = 25
    unsupported: list[str] = []
    for name, (edge_x, top, bottom) in module_zones.items():
        supported = any(
            abs(x - edge_x) <= horizontal_tolerance
            and top - vertical_tolerance <= y <= bottom + vertical_tolerance
            for x, y in points
        )
        if not supported:
            unsupported.append(name)

    assert not unsupported, f"Side modules without nearby canonical route support: {unsupported}"


def test_side_card_alignment_does_not_replace_canonical_route_layers() -> None:
    html = _splash_html()

    expected_layers = {
        "cyan": "/console/splash_routes_cyan.svg",
        "teal": "/console/splash_routes_teal.svg",
        "lime": "/console/splash_routes_lime.svg",
        "amber": "/console/splash_routes_amber.svg",
        "violet": "/console/splash_routes_violet.svg",
    }

    for family, source in expected_layers.items():
        assert f'data-canonical-route-layer="{family}"' in html
        assert f'src="{source}"' in html

    assert "Math.random(" not in html
    assert "procedural" not in html.lower()


def test_side_cards_preserve_reference_roles_and_color_zones() -> None:
    html = _splash_html()

    expected_modules = [
        ("c1", "governance", "GOVERNANCE"),
        ("c2", "supervision", "SUPERVISION"),
        ("c3", "calibration", "CALIBRATION"),
        ("c4", "orchestration", "ORCHESTRATION"),
        ("r1", "routing", "ROUTING"),
        ("r2", "policy-engine", "POLICY ENGINE"),
        ("r3", "feedback-loop", "FEEDBACK LOOP"),
        ("r4", "control-gates", "CONTROL GATES"),
    ]
    for css_class, slug, title in expected_modules:
        assert f'class="card {css_class}" data-module="{slug}"' in html
        assert f"<h3>{title}</h3>" in html

    expected_color_markers = [
        ".card.c1{color:#21dbff}",
        ".card.c2{color:#18f5e9}",
        ".card.c3{color:#a6ff43}",
        ".card.c4{color:#d36cff}",
        ".card.r1,.card.r2{color:#ffad1f}",
        ".card.r3{color:#18f5e9}",
        ".card.r4{color:#d36cff}",
    ]
    missing_colors = [marker for marker in expected_color_markers if marker not in html]
    assert not missing_colors, f"Missing reference module color markers: {missing_colors}"

    stale_titles = [
        "Multi-Agent Orchestration",
        "Repair Loop",
        "Failure Recovery",
        "Policy Enforcement",
        "Observability",
        "Adversarial Validation",
        "Supervisor Feedback",
    ]
    stale = [title for title in stale_titles if title in html]
    assert not stale, f"Stale non-reference side module titles found: {stale}"
