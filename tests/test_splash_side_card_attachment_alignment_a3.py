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
