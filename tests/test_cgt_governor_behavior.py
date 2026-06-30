import asyncio
import json
from types import SimpleNamespace

import processual_api.cgt_governor as cgt_package
import processual_api.routers.cgt_governor as cgt_router
from processual_api.cgt_governor.data.storage import JsonlEvaluationStore


class _FakeRank:
    value = "stable"

class _FakeFateVector(dict):
    def __missing__(self, key):
        self[key] = 0.0
        return 0.0

class _FakeScores(dict):
    def __missing__(self, key):
        self[key] = 0.0
        return 0.0


class _FakeResult:
    rank = _FakeRank()
    reward = 0.91
    policy = "accept"
    policy_label = "Accept"
    repair_prompt = None
    fate_vector = _FakeFateVector(
        {
            "compatibility": 0.9,
            "clarity": 0.9,
            "coherence": 0.8,
            "stability": 0.82,
            "grounding": 0.84,
            "novelty": 0.7,
            "usefulness": 0.88,
            "safety": 0.95,
        }
    )



class _FakeAction:
    value = "keep"


class _FakePolicyDecision:
    action = _FakeAction()
    action_label = "Keep - Accept Response"


class _FakeStore:
    def __init__(self):
        self.entries = []
        self.appended = []

    def append(self, entry):
        self.appended.append(entry)
        self.entries.append(entry)

    def __len__(self):
        return len(self.entries)


class _FakePolicyEngine:
    def __init__(self):
        self.decide_calls = []
        self.record_calls = []
        self.history = []
        self.action_distribution = {}

    def decide(self, **kwargs):
        self.decide_calls.append(kwargs)
        return _FakePolicyDecision()

    def record(self, decision, eval_id="", reason=""):
        self.record_calls.append(
            {"decision": decision, "eval_id": eval_id, "reason": reason}
        )
        self.history.append(SimpleNamespace(action=decision.action))
        self.action_distribution[decision.action.value] = (
            self.action_distribution.get(decision.action.value, 0) + 1
        )


def test_evaluate_and_record_uses_policy_signature_encryption_and_store(monkeypatch):
    fake_store = _FakeStore()
    fake_engine = _FakePolicyEngine()
    encrypted_calls = []
    signed_payloads = []

    def fake_govern_answer(*args, **kwargs):
        return _FakeResult()

    def fake_build_response(result, language):
        return {
            "rank": result.rank.value,
            "reward": result.reward,
            "policy": result.policy,
            "policy_label": result.policy_label,
            "language": language,
        }

    def fake_sign_response(payload):
        signed_payloads.append(payload)
        return "test-signature"

    def fake_encrypt_log_entry(entry, key):
        encrypted_calls.append({"entry": dict(entry), "key": key})
        return entry

    monkeypatch.setattr(cgt_package, "govern_answer", fake_govern_answer)
    monkeypatch.setattr(cgt_router, "_build_response", fake_build_response)
    monkeypatch.setattr(cgt_router, "sign_response", fake_sign_response)
    monkeypatch.setattr(cgt_router, "encrypt_log_entry", fake_encrypt_log_entry)
    monkeypatch.setattr(cgt_router, "eval_store", fake_store)
    monkeypatch.setattr(cgt_router, "runtime_policy_engine", fake_engine)
    monkeypatch.setattr(
        JsonlEvaluationStore,
        "_generate_eval_id",
        staticmethod(lambda: "eval_test_06b"),
    )

    result = cgt_router._evaluate_and_record(
        answer="A governed answer.",
        language="en",
        scores=_FakeScores(
            {
                "compatibility": 0.9,
                "clarity": 0.9,
                "coherence": 0.8,
                "stability": 0.82,
                "grounding": 0.84,
                "novelty": 0.7,
                "usefulness": 0.88,
                "safety": 0.95,
            }
        ),
        reason="test_06b",
    )


    assert result["signature"] == "test-signature"
    assert result["governance_action"] == "keep"
    assert result["action_label"] == "Keep - Accept Response"

    assert signed_payloads == [result["response_data"]]
    assert fake_engine.decide_calls
    assert fake_engine.decide_calls[0]["rank"] == "stable"
    assert fake_engine.decide_calls[0]["reward"] == 0.91
    assert fake_engine.record_calls[0]["reason"] == "test_06b"

    assert encrypted_calls
    assert encrypted_calls[0]["entry"]["eval_id"] == "eval_test_06b"
    assert fake_store.appended
    assert fake_store.appended[0]["eval_id"] == "eval_test_06b"


def test_governor_status_and_toggle_reflect_runtime_state(monkeypatch):
    original_state = dict(cgt_router._gov_state)
    fake_store = _FakeStore()
    fake_store.append({"eval_id": "eval_existing_1"})

    class _FakeRegistry:
        def list_providers(self):
            return ["fake-provider"]

        def default(self):
            return SimpleNamespace(provider_name="fake-provider")

    monkeypatch.setattr(cgt_router, "eval_store", fake_store)
    monkeypatch.setattr(cgt_router, "adapter_registry", _FakeRegistry())

    try:
        cgt_router._gov_state["enabled"] = True

        status = asyncio.run(
            cgt_router.governor_status(current_user={"sub": "test-user"})
        )

        assert status["enabled"] is True
        assert status["evaluation_count"] == 1
        assert status["providers"] == ["fake-provider"]
        assert status["default_provider"] == "fake-provider"

        toggle_result = asyncio.run(
            cgt_router.governor_toggle(
                cgt_router.ToggleRequest(enabled=False),
                current_user={"sub": "test-user"},
            )
        )

        assert toggle_result == {"enabled": False}
        assert cgt_router._gov_state["enabled"] is False
    finally:
        cgt_router._gov_state.clear()
        cgt_router._gov_state.update(original_state)


def test_analyze_returns_raw_analyzer_scores(monkeypatch):
    import processual_api.cgt_governor.analyzer as analyzer

    fake_scores = {
        "test_metric": 0.77,
        "clarity": 0.91,
        "coherence": 0.88,
    }

    def fake_analyze_cgt(client_query, answer, language="en"):
        assert client_query == ""
        assert answer == "Analyze this answer."
        assert language == "en"
        return fake_scores

    monkeypatch.setattr(analyzer, "analyze_cgt", fake_analyze_cgt)

    result = asyncio.run(
        cgt_router.analyze(
            cgt_router.AnalyzeRequest(
                answer="Analyze this answer.",
                language="en",
            ),
            current_user={"sub": "test-user"},
        )
    )

    serialized = json.dumps(result, default=str)
    assert "test_metric" in serialized
    assert "0.77" in serialized