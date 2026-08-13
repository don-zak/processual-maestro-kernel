from __future__ import annotations

import json
from pathlib import Path

import pytest

from processual_api.cgt_governor.data.telemetry_storage import JsonlTelemetryStore


def test_load_existing_skips_invalid_lines_and_respects_maxlen(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"ts": "2026-01-01", "metric": "first", "value": 1}),
                "not-json",
                json.dumps({"ts": "2026-01-02", "metric": "second", "value": 2}),
                json.dumps({"ts": "2026-01-03", "metric": "third", "value": 3}),
                "",
            ]
        ),
        encoding="utf-8",
    )

    store = JsonlTelemetryStore(path=path, maxlen=2)

    assert len(store) == 2
    assert [entry["metric"] for entry in store.entries] == ["second", "third"]
    assert store.path == path


def test_missing_file_starts_with_empty_buffer(tmp_path: Path) -> None:
    store = JsonlTelemetryStore(path=tmp_path / "missing.jsonl")

    assert len(store) == 0
    assert store.entries == []


def test_ingest_appends_buffer_and_jsonl_file(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    store = JsonlTelemetryStore(path=path)

    store.ingest("latency", 1.25, {"provider": "mock"})
    store.ingest("count", 2.0)

    assert len(store) == 2
    assert store.entries[0]["metric"] == "latency"
    assert store.entries[0]["labels"] == {"provider": "mock"}
    assert store.entries[1]["labels"] == {}

    persisted = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [entry["metric"] for entry in persisted] == ["latency", "count"]
    assert persisted[0]["value"] == pytest.approx(1.25)
    assert persisted[0]["ts"].endswith("+00:00")


def test_query_filters_metric_since_and_limit(tmp_path: Path) -> None:
    store = JsonlTelemetryStore(path=tmp_path / "telemetry.jsonl")
    store._buffer.extend(
        [
            {"ts": "2026-01-01T00:00:00+00:00", "metric": "a", "value": 1},
            {"ts": "2026-01-02T00:00:00+00:00", "metric": "b", "value": 2},
            {"ts": "2026-01-03T00:00:00+00:00", "metric": "a", "value": 3},
            {"ts": "2026-01-04T00:00:00+00:00", "metric": "a", "value": 4},
        ]
    )

    assert [entry["value"] for entry in store.query(metric="a")] == [1, 3, 4]
    assert [entry["value"] for entry in store.query(since="2026-01-03T00:00:00+00:00")] == [3, 4]
    assert [entry["value"] for entry in store.query(metric="a", since="2026-01-02T00:00:00+00:00", limit=1)] == [4]
    assert [entry["value"] for entry in store.query(limit=2)] == [3, 4]


def test_ingest_keeps_in_memory_entry_when_persistence_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JsonlTelemetryStore(path=tmp_path / "telemetry.jsonl")

    def fail_open(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr(Path, "open", fail_open)

    store.ingest("survives", 7.0)

    assert len(store) == 1
    assert store.entries[0]["metric"] == "survives"


def test_load_existing_open_failure_is_nonfatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "telemetry.jsonl"
    path.write_text("{}\n", encoding="utf-8")

    def fail_open(*args, **kwargs):
        raise OSError("cannot read")

    monkeypatch.setattr(Path, "open", fail_open)

    store = JsonlTelemetryStore(path=path)

    assert store.entries == []


def test_clear_empties_buffer_and_removes_file(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    store = JsonlTelemetryStore(path=path)
    store.ingest("metric", 1.0)
    assert path.exists()

    store.clear()

    assert len(store) == 0
    assert store.entries == []
    assert not path.exists()


def test_clear_ignores_unlink_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "telemetry.jsonl"
    store = JsonlTelemetryStore(path=path)
    store._buffer.append({"metric": "x"})

    def fail_unlink(*args, **kwargs):
        raise OSError("cannot remove")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    store.clear()

    assert store.entries == []
