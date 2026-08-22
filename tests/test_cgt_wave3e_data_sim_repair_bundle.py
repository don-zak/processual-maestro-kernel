from __future__ import annotations

import json

import pytest

from processual_api.cgt_governor.data.telemetry_storage import JsonlTelemetryStore
from processual_api.cgt_governor.math_utils import clamp01, lerp, sigmoid, softplus
from processual_api.cgt_governor.repair import (
    build_distortion_repair_prompt,
    build_hybrid_repair_prompt,
    build_transient_deepen_prompt,
)
from processual_api.cgt_governor.simulation.engine import (
    AgentEvaluation,
    SimulationEngine,
    SimulationResult,
)
from processual_api.integrations.private_evaluation_boundary import PrivateEvaluationUnavailableError


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


@pytest.mark.parametrize("use_analyzer", [False, True])
def test_simulation_engine_fails_closed_without_sanitized_private_decisions(use_analyzer: bool) -> None:
    with pytest.raises(PrivateEvaluationUnavailableError, match="private_evaluation_unavailable"):
        SimulationEngine.run(language="ar", use_analyzer=use_analyzer)


def test_simulation_engine_does_not_expose_legacy_local_catalog_authority() -> None:
    import processual_api.cgt_governor.simulation.engine as engine_module

    assert not hasattr(engine_module, "ALL_AGENTS")
    assert not hasattr(engine_module, "ALL_SCENARIOS")
    assert SimulationEngine._counter == 0


def test_legacy_simulation_result_shapes_remain_import_compatible() -> None:
    assert AgentEvaluation.__dataclass_fields__["repair_prompt"].default is None
    assert tuple(SimulationResult.__dataclass_fields__) == (
        "simulation_id",
        "ts",
        "evaluations",
        "rank_distribution",
        "avg_reward",
        "highest_agent",
        "lowest_agent",
        "risk_count",
    )
