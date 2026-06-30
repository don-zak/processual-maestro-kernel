import json
import logging

from processual_api.cgt_governor.data.storage import JsonlEvaluationStore


def test_jsonl_evaluation_store_appends_dict_and_json_string(tmp_path, monkeypatch):
    path = tmp_path / "governance_runs.jsonl"
    generated_ids = iter(["eval_test_001", "eval_test_002"])

    monkeypatch.setattr(
        JsonlEvaluationStore,
        "_generate_eval_id",
        staticmethod(lambda: next(generated_ids)),
    )

    store = JsonlEvaluationStore(path=path, maxlen=10)

    first_entry = {
        "rank": "stable",
        "reward": 0.91,
        "policy": "accept",
        "policy_label": "قبول",
    }
    second_entry = {
        "eval_id": "eval_existing",
        "rank": "hybrid",
        "reward": 0.42,
    }

    store.append(first_entry)
    store.append(json.dumps(second_entry))

    assert len(store) == 2
    assert store.entries[0]["eval_id"] == "eval_test_001"
    assert store[0]["rank"] == "stable"
    assert store[1]["eval_id"] == "eval_existing"
    assert store[1]["rank"] == "hybrid"
    assert store.path == path

    persisted_text = path.read_text(encoding="utf-8")
    assert "قبول" in persisted_text

    persisted_lines = persisted_text.splitlines()
    assert len(persisted_lines) == 2
    assert json.loads(persisted_lines[0])["eval_id"] == "eval_test_001"
    assert json.loads(persisted_lines[1])["eval_id"] == "eval_existing"


def test_jsonl_evaluation_store_loads_existing_and_skips_malformed_lines(
    tmp_path,
    caplog,
):
    path = tmp_path / "governance_runs.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"eval_id": "eval_1", "rank": "stable"}),
                "{malformed-json",
                "",
                json.dumps({"eval_id": "eval_2", "rank": "extinct"}),
            ]
        ),
        encoding="utf-8",
    )

    with caplog.at_level(
        logging.WARNING,
        logger="processual_api.cgt_governor.data.storage",
    ):
        store = JsonlEvaluationStore(path=path, maxlen=10)

    assert len(store) == 2
    assert [entry["eval_id"] for entry in store.entries] == ["eval_1", "eval_2"]
    assert store[0]["rank"] == "stable"
    assert store[1]["rank"] == "extinct"
    assert "Skipping malformed JSONL line" in caplog.text


def test_jsonl_evaluation_store_extend_clear_and_maxlen(tmp_path, monkeypatch):
    path = tmp_path / "governance_runs.jsonl"
    generated_ids = iter(["eval_auto_1", "eval_auto_2", "eval_auto_3"])

    monkeypatch.setattr(
        JsonlEvaluationStore,
        "_generate_eval_id",
        staticmethod(lambda: next(generated_ids)),
    )

    store = JsonlEvaluationStore(path=path, maxlen=2)

    store.extend(
        [
            {"rank": "stable", "reward": 0.8},
            {"rank": "hybrid", "reward": 0.5},
            {"rank": "extinct", "reward": 0.1},
        ]
    )

    assert len(store) == 2
    assert [entry["rank"] for entry in store.entries] == ["hybrid", "extinct"]
    assert store.entries[0]["eval_id"] == "eval_auto_2"
    assert store.entries[1]["eval_id"] == "eval_auto_3"

    persisted_lines = path.read_text(encoding="utf-8").splitlines()
    assert len(persisted_lines) == 3

    store.clear()

    assert len(store) == 0
    assert store.entries == []
    assert not path.exists()
