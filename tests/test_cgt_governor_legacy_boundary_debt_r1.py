from __future__ import annotations

from pathlib import Path


_CLEAN_OPERATIONAL_PATHS = (
    Path("processual_api/cgt_governor/governor.py"),
    Path("processual_api/cgt_governor/gateway/engine.py"),
    Path("processual_api/cgt_governor/simulation/engine.py"),
)
_LEGACY_ROUTER = Path("processual_api/routers/cgt_governor.py")


def test_sanitized_operational_paths_do_not_reintroduce_raw_score_pipeline() -> None:
    forbidden = (
        "_resolve_scores(",
        "analyze_cgt(",
        "result.fate",
        '"scores": scores',
        "add_evaluation(",
    )
    for path in _CLEAN_OPERATIONAL_PATHS:
        source = path.read_text("utf-8")
        for token in forbidden:
            assert token not in source, f"{path} reintroduced legacy token {token!r}"


def test_remaining_raw_score_boundary_debt_is_explicitly_quarantined_to_legacy_router() -> None:
    source = _LEGACY_ROUTER.read_text("utf-8")

    # This assertion is intentionally a debt marker, not approval of the legacy
    # contract. Removing any of these tokens means the router migration has
    # advanced and this test must be tightened rather than silently relocated.
    known_debt = (
        "def _resolve_scores(",
        '"fate_vector": {',
        '"reward": result.reward',
        '"scores": scores',
    )
    for token in known_debt:
        assert token in source

    # The public neutral boundary itself must never move into this legacy router.
    assert "private_integrations" not in source
    assert "cgtlib.private" not in source
