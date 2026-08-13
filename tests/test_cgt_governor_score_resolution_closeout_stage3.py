from __future__ import annotations

from types import SimpleNamespace

import processual_api.cgt_governor.analyzer as analyzer_module
import processual_api.routers.cgt_governor as cgt_router


def test_resolve_scores_prefers_explicit_then_auto_then_fallback(monkeypatch) -> None:
    calls = []

    def fake_analyze(client_query: str, answer: str, *, language: str):
        calls.append((client_query, answer, language))
        return {
            "compatibility": 0.11,
            "coherence": 0.22,
            "usefulness": 0.33,
        }

    monkeypatch.setattr(analyzer_module, "analyze_cgt", fake_analyze)
    request = cgt_router.GovernRequest(
        answer="answer",
        client_query="query",
        language="ar",
        compatibility=0.91,
        shock=0.77,
    )

    resolved = cgt_router._resolve_scores(request)

    assert calls == [("query", "answer", "ar")]
    assert resolved["compatibility"] == 0.91
    assert resolved["coherence"] == 0.22
    assert resolved["usefulness"] == 0.33
    assert resolved["shock"] == 0.77
    assert resolved["fatigue"] == cgt_router._SCORE_FALLBACKS["fatigue"]
    assert set(resolved) == set(cgt_router._SCORE_FALLBACKS)


def test_resolve_scores_uses_fallbacks_without_client_query(monkeypatch) -> None:
    calls = []

    def fake_analyze(*args, **kwargs):
        calls.append((args, kwargs))
        return {"compatibility": 0.01}

    monkeypatch.setattr(analyzer_module, "analyze_cgt", fake_analyze)
    request = cgt_router.GovernRequest(answer="answer", compatibility=0.8)

    resolved = cgt_router._resolve_scores(request)

    assert calls == []
    assert resolved["compatibility"] == 0.8
    for key, fallback in cgt_router._SCORE_FALLBACKS.items():
        if key != "compatibility":
            assert resolved[key] == fallback


def test_build_response_serializes_fate_rank_and_optional_policy_metadata() -> None:
    fate = SimpleNamespace(
        stability=0.9,
        hybridity=0.1,
        distortion=0.2,
        extinction=0.0,
        collapse=0.0,
        flourishing=0.8,
        transient=0.3,
    )
    rank = SimpleNamespace(value="stable")
    result = SimpleNamespace(
        fate=fate,
        rank=rank,
        reward=0.88,
        policy="accept",
        policy_label="Accept",
        policy_description="Keep the answer.",
        repair_prompt=None,
    )

    payload = cgt_router._build_response(result, "en")

    assert payload == {
        "fate_vector": {
            "stability": 0.9,
            "hybridity": 0.1,
            "distortion": 0.2,
            "extinction": 0.0,
            "collapse": 0.0,
            "flourishing": 0.8,
            "transient": 0.3,
        },
        "rank": "stable",
        "reward": 0.88,
        "policy": "accept",
        "policy_label": "Accept",
        "policy_description": "Keep the answer.",
        "repair_prompt": None,
    }


def test_build_response_defaults_missing_policy_metadata() -> None:
    result = SimpleNamespace(
        fate=SimpleNamespace(
            stability=0.1,
            hybridity=0.2,
            distortion=0.3,
            extinction=0.4,
            collapse=0.5,
            flourishing=0.6,
            transient=0.7,
        ),
        rank=SimpleNamespace(value="hybrid"),
        reward=0.4,
        policy="repair",
        repair_prompt="repair this",
    )

    payload = cgt_router._build_response(result, "ar")

    assert payload["policy_label"] == ""
    assert payload["policy_description"] == ""
    assert payload["repair_prompt"] == "repair this"
