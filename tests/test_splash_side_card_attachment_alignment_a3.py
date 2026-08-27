from pathlib import Path
import re


SPLASH = Path("processual_api/static/splash.html")


def _splash_html() -> str:
    return SPLASH.read_text(encoding="utf-8")


def test_side_card_inner_edges_align_with_reference_attachment_zones() -> None:
    html = _splash_html()

    width_match = re.search(r"\.card\{[^}]*width:(\d+)px", html)
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
    left = int(left_match.group(1))
    right = int(right_match.group(1))

    assert card_width == 244
    assert left + card_width == 415
    assert stage_width - right - card_width == 1240


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
