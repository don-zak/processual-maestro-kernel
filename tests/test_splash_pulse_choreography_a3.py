from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "processual_api" / "static" / "splash.html"


def test_pulse_choreography_is_semantically_bound_to_active_family() -> None:
    source = SPLASH.read_text(encoding="utf-8")

    required = (
        "const cx=824.5,cy=428,maxR=690,duration=4300,rest=850,cycle=duration+rest",
        "cycleIndex=Math.floor(total/cycle)%pulses.length",
        "active=pulses[cycleIndex]",
        "p.head.style.opacity=enabled?'.94':'0'",
        "p.tail.style.opacity=enabled?'.58':'0'",
        "p.head.style.maskImage=headMask",
        "p.tail.style.maskImage=tailMask",
        "core.classList.toggle('pulse-source',t<.32)",
        "const receiverWindow=t>.68&&t<.96",
        "card.classList.toggle('receiving',receiverWindow&&card.dataset.routeFamily===active.family)",
        "core.style.setProperty('--pulse-color',familyColors[active.family])",
        "requestAnimationFrame(frame)",
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


def test_static_cyan_rebalance_does_not_dim_animated_pulse_layer() -> None:
    source = SPLASH.read_text(encoding="utf-8")

    assert ".route-layer.cyan{opacity:.62;filter:brightness(.58) drop-shadow(0 0 .8px currentColor)}" in source
    assert ".route-layer.cyan,.pulse-layer.cyan{color:var(--cyan)}" in source
    assert ".pulse-layer.pulse-head{filter:drop-shadow(1.4px 0 0 currentColor)" in source
    assert ".pulse-layer.pulse-tail{filter:drop-shadow(.65px 0 0 currentColor)" in source
    assert ".pulse-layer.cyan{opacity:.62" not in source
    assert ".pulse-layer.cyan{filter:brightness(.58)" not in source
