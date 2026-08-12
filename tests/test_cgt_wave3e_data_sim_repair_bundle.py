from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from processual_api.cgt_governor.data.telemetry_storage import JsonlTelemetryStore
from processual_api.cgt_governor.math_utils import clamp01, lerp, sigmoid, softplus
from processual_api.cgt_governor.repair import (
    build_distortion_repair_prompt,
    build_hybrid_repair_prompt,
    build_transient_deepen_prompt,
)
from processual_api.cgt_governor.simulation.engine import SimulationEngine


def test_telemetry_store_load_query_limit_and_clear(tmp_path) -> None:
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"ts": "2026-01-01T00:00:00+00:00", "metric": "latency", "value": 1.0}),
                "not-json",
                "",
                json.dumps({"ts": "2026-01-02T00:00:00+00:00", "metric": "quality", "value": 2.0}),
                json.dumps({"ts": "2026-01-03T00:00:00+00:00", "metric": "latency", "value": 3.0}),
            ]
        ),
        encoding="utf-8",
    )

    store = JsonlTelemetryStore(path=path, maxlen=2)

    assert len(store) == 2
    assert [entry["metric"] for entry in store.entries] == ["quality", "latency"]
    assert store.path == path
    assert store.query(metric="latency") == [store.entries[-1]]
    assert store.query(since="2026-01-03", limit=1) == [store.entries[-1]]
    assert store.query(limit=1) == [store.entries[-1]]

    store.clear()
    assert len(store) == 0
    assert store.entries == []
    assert not path.exists()


def test_telemetry_store_ingest_persists_labels_and_respects_maxlen(tmp_path) -> None:
    path = tmp_path / "nested" / "telemetry.jsonl"
    store = JsonlTelemetryStore(path=path, maxlen=2)

    store.ingest("m1", 1.5, {"agent": "a"})
    store.ingest("m2", 2.5)
    store.ingest("m3", 3.5, {})

    assert len(store) == 2
    assert [entry["metric"] for entry in store.entries] == ["m2", "m3"]
    assert store.entries[0]["labels"] == {}
    assert store.entries[1]["value"] == 3.5

    persisted = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(persisted) == 3
    assert persisted[0]["labels"] == {"agent": "a"}
    assert persisted[0]["ts"].endswith("+00:00")


def test_telemetry_store_handles_io_errors_without_raising(tmp_path) -> None:
    directory_path = tmp_path / "as-directory"
    directory_path.mkdir()

    store = JsonlTelemetryStore(path=directory_path)
    assert len(store) == 0

    store.ingest("metric", 1.0)
    assert len(store) == 1

    store.clear()
    assert len(store) == 0
    assert directory_path.exists()


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-2.0, 0.0), (0.0, 0.0), (0.25, 0.25), (1.0, 1.0), (3.0, 1.0)],
)
def test_clamp01(value: float, expected: float) -> None:
    assert clamp01(value) == expected


def test_math_helpers_cover_core_behavior() -> None:
    assert sigmoid(0.0) == pytest.approx(0.5)
    assert sigmoid(2.0) > sigmoid(-2.0)
    assert softplus(0.0) == pytest.approx(0.6931471805599453)
    assert softplus(2.0) > 2.0
    assert lerp(10.0, 20.0, -1.0) == 10.0
    assert lerp(10.0, 20.0, 0.25) == 12.5
    assert lerp(10.0, 20.0, 2.0) == 20.0


@pytest.mark.parametrize(
    ("builder", "english_marker", "arabic_marker"),
    [
        (build_hybrid_repair_prompt, "Preserve the correct core", "حافظ على النواة الصحيحة"),
        (build_distortion_repair_prompt, "Rebuild from scratch", "أعد بناءه من الصفر"),
        (build_transient_deepen_prompt, "Deepen it without unnecessary length", "عمّقه دون إطالته"),
    ],
)
def test_repair_prompt_builders_cover_english_and_arabic(builder, english_marker: str, arabic_marker: str) -> None:
    answer = "ORIGINAL ANSWER"

    english = builder(answer)
    arabic = builder(answer, language="ar")

    assert answer in english
    assert answer in arabic
    assert english_marker in english
    assert arabic_marker in arabic


def _agent(agent_id: str, language: str = "en") -> SimpleNamespace:
    return SimpleNamespace(agent_id=agent_id, language=language)


def _result(rank: str, reward: float, repair_prompt: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        rank=SimpleNamespace(value=rank),
        reward=reward,
        policy=f"policy-{rank}",
        policy_label=f"label-{rank}",
        repair_prompt=repair_prompt,
        fate=SimpleNamespace(
            stability=0.1,
            hybridity=0.2,
            distortion=0.3,
            extinction=0.4,
            collapse=0.5,
            flourishing=0.6,
            transient=0.7,
        ),
    )


def test_simulation_engine_legacy_mode_aggregates_and_skips_missing_scenario(monkeypatch: pytest.MonkeyPatch) -> None:
    import processual_api.cgt_governor.governor as governor_module
    import processual_api.cgt_governor.simulation.engine as engine_module

    agents = [_agent("fin-ar-01", "ar"), _agent("rand-en-06"), _agent("missing")]
    scenarios = {
        "fin-ar-01": SimpleNamespace(title="Finance"),
        "rand-en-06": SimpleNamespace(title="Random"),
    }
    calls: list[dict] = []
    results = iter([_result("flourishing", 0.9), _result("extinct", -0.8, "repair")])

    def fake_govern_answer(**kwargs):
        calls.append(kwargs)
        return next(results)

    monkeypatch.setattr(engine_module, "ALL_AGENTS", agents)
    monkeypatch.setattr(engine_module, "ALL_SCENARIOS", scenarios)
    monkeypatch.setattr(governor_module, "govern_answer", fake_govern_answer)
    monkeypatch.setattr(SimulationEngine, "_counter", 0)

    result = SimulationEngine.run(language="ar", use_analyzer=False)

    assert result.simulation_id == "sim-0001"
    assert len(result.evaluations) == 2
    assert result.rank_distribution == {"flourishing": 1, "extinct": 1}
    assert result.avg_reward == pytest.approx(0.05)
    assert result.highest_agent == "fin-ar-01"
    assert result.lowest_agent == "rand-en-06"
    assert result.risk_count == 1
    assert result.ts.endswith("+00:00")
    assert result.evaluations[1].repair_prompt == "repair"
    assert result.evaluations[0].fate_vector == {
        "stability": 0.1,
        "hybridity": 0.2,
        "distortion": 0.3,
        "extinction": 0.4,
        "collapse": 0.5,
        "flourishing": 0.6,
        "transient": 0.7,
    }
    assert calls[0]["language"] == "ar"
    assert calls[0]["speed"] == 0.5
    assert calls[0]["compatibility"] == pytest.approx(0.88)
    assert calls[1]["hallucination"] == 0.0


def test_simulation_engine_analyzer_mode_uses_analysis_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    import processual_api.cgt_governor.analyzer as analyzer_module
    import processual_api.cgt_governor.governor as governor_module
    import processual_api.cgt_governor.simulation.engine as engine_module

    agent = _agent("tech-en-05", "en")
    monkeypatch.setattr(engine_module, "ALL_AGENTS", [agent])
    monkeypatch.setattr(engine_module, "ALL_SCENARIOS", {"tech-en-05": SimpleNamespace(title="Debug API")})

    analyze_calls: list[dict] = []
    govern_calls: list[dict] = []

    def fake_analyze_cgt(**kwargs):
        analyze_calls.append(kwargs)
        return {"compatibility": 0.77, "coherence": 0.66}

    def fake_govern_answer(**kwargs):
        govern_calls.append(kwargs)
        return _result("stable", 0.5)

    monkeypatch.setattr(analyzer_module, "analyze_cgt", fake_analyze_cgt)
    monkeypatch.setattr(governor_module, "govern_answer", fake_govern_answer)

    result = SimulationEngine.run(language="ar", use_analyzer=True)

    assert len(result.evaluations) == 1
    assert result.avg_reward == 0.5
    assert result.highest_agent == "tech-en-05"
    assert result.lowest_agent == "tech-en-05"
    assert result.risk_count == 0
    assert analyze_calls[0]["client_query"] == "Debug API (ar)"
    assert analyze_calls[0]["language"] == "en"
    assert "422 Validation Error" in analyze_calls[0]["agent_response"]
    assert govern_calls[0]["compatibility"] == 0.77
    assert govern_calls[0]["coherence"] == 0.66
    assert govern_calls[0]["language"] == "en"


def test_simulation_engine_empty_run_has_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    import processual_api.cgt_governor.simulation.engine as engine_module

    monkeypatch.setattr(engine_module, "ALL_AGENTS", [_agent("no-scenario")])
    monkeypatch.setattr(engine_module, "ALL_SCENARIOS", {})

    result = SimulationEngine.run(use_analyzer=False)

    assert result.evaluations == []
    assert result.rank_distribution == {}
    assert result.avg_reward == 0.0
    assert result.highest_agent is None
    assert result.lowest_agent is None
    assert result.risk_count == 0
