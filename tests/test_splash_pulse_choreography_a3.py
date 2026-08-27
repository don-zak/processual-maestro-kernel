from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "processual_api" / "static" / "splash.html"


def test_pulse_choreography_is_semantically_bound_to_active_family() -> None:
    source = SPLASH.read_text(encoding="utf-8")

    required = (
        "const cx=824.5,cy=428,maxR=690,duration=4300,rest=850,cycle=duration+rest",
        "cycleIndex=Math.floor(total/cycle)%pulses.length",
        "active=pulses[cycleIndex]",
        "core.classList.toggle('pulse-source',t<.32)",
        "const receiverWindow=t>.68&&t<.96",
        "card.classList.toggle('receiving',receiverWindow&&card.dataset.routeFamily===active.family)",
        "core.style.setProperty('--pulse-color',familyColors[active.family])",
    )
    missing = [marker for marker in required if marker not in source]
    assert not missing, f"Missing deterministic pulse choreography markers: {missing}"


def test_pulse_choreography_never_changes_canonical_route_geometry() -> None:
    source = SPLASH.read_text(encoding="utf-8")

    assert "baseLayers=[...stage.querySelectorAll('.route-layer')]" in source
    assert "tail=layer.cloneNode(false)" in source
    assert "head=layer.cloneNode(false)" in source
    assert "p.head.style.maskImage=headMask" in source
    assert "p.tail.style.maskImage=tailMask" in source
    assert "createElementNS" not in source
    assert "setAttribute('d'" not in source
    assert 'setAttribute("d"' not in source
