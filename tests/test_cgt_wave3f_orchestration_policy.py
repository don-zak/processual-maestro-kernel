from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import processual_api.cgt_governor.adapters.execution_fanout as fanout_module
import processual_api.cgt_governor.governor as governor_module
from processual_api.cgt_governor.adapters.execution_fanout import (
    ExecutionFanoutAuthorityUnavailableError,
    ExecutionFanoutDecision,
    ExecutionFanoutLeaseLostError,
    ExecutionFanoutPolicy,
    ExecutionFanoutReservation,
    ExecutionFanoutSaturatedError,
    InMemoryExecutionFanoutBackend,
    RedisExecutionFanoutBackend,
)
from processual_api.cgt_governor.policy.engine import (
    GovernanceAction,
    PolicyContext,
    PolicyDecision,
    PolicyEngine,
    map_to_governance_action,
)
from processual_api.integrations.private_evaluation_boundary import (
    PrivateEvaluationUnavailableError,
    SanitizedPrivateDecision,
)


def test_execution_fanout_policy_from_env_clamps_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTION_FANOUT_ENABLED", "FALSE")
    monkeypatch.setenv("EXECUTION_FANOUT_GLOBAL_LIMIT", "0")
    monkeypatch.setenv("EXECUTION_FANOUT_PROVIDER_LIMIT", "-4")
    monkeypatch.setenv("EXECUTION_FANOUT_LEASE_SECONDS", "1")
    monkeypatch.setenv("EXECUTION_FANOUT_WAIT_MS", "-2")
    monkeypatch.setenv("EXECUTION_FANOUT_RETRY_MS", "1")

    policy = ExecutionFanoutPolicy.from_env()

    assert policy.enabled is False
    assert policy.global_limit == 1
    assert policy.provider_limit == 1
    assert policy.lease_seconds == 5
    assert policy.wait_ms == 0
    assert policy.retry_ms == 5


def test_provider_key_is_normalized_and_stable() -> None:
    assert fanout_module._provider_key(" OpenAI ") == fanout_module._provider_key("openai")
    assert fanout_module._provider_key("OpenAI") != fanout_module._provider_key("Anthropic")
    assert len(fanout_module._provider_key("provider")) == 24


@pytest.mark.asyncio
async def test_inmemory_cleanup_release_and_wrong_provider_renew(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = InMemoryExecutionFanoutBackend()
    now = 10.0
    monkeypatch.setattr(fanout_module.time, "monotonic", lambda: now)

    reservation = ExecutionFanoutReservation("lease-a", "provider-a")
    assert (
        await backend.reserve(
            reservation=reservation,
            global_limit=2,
            provider_limit=2,
            lease_seconds=5,
        )
    ).admitted is True

    wrong = ExecutionFanoutReservation("lease-a", "provider-b")
    assert await backend.renew(wrong, lease_seconds=5) is False

    await backend.release(reservation)
    assert await backend.renew(reservation, lease_seconds=5) is False

    await backend.reserve(
        reservation=reservation,
        global_limit=2,
        provider_limit=2,
        lease_seconds=5,
    )
    now = 16.0
    replacement = ExecutionFanoutReservation("lease-b", "provider-a")
    decision = await backend.reserve(
        reservation=replacement,
        global_limit=1,
        provider_limit=1,
        lease_seconds=5,
    )
    assert decision.admitted is True
    assert decision.global_used == 1
    assert decision.provider_used == 1


class _FakeRedis:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.calls: list[tuple] = []

    async def eval(self, *args):
        self.calls.append(args)
        return self.results.pop(0)


@pytest.mark.asyncio
async def test_redis_backend_reserve_renew_release_and_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fanout_module.time, "time", lambda: 100.0)
    redis = _FakeRedis([[0, 7, 3, 1], [0, 7, 3, 2], [1, 2, 1, 0], 1, 1])
    backend = RedisExecutionFanoutBackend(redis)
    reservation = ExecutionFanoutReservation("lease", "provider-key")

    global_reject = await backend.reserve(
        reservation=reservation,
        global_limit=7,
        provider_limit=4,
        lease_seconds=10,
    )
    provider_reject = await backend.reserve(
        reservation=reservation,
        global_limit=8,
        provider_limit=3,
        lease_seconds=10,
    )
    admitted = await backend.reserve(
        reservation=reservation,
        global_limit=8,
        provider_limit=4,
        lease_seconds=10,
    )
    renewed = await backend.renew(reservation, lease_seconds=10)
    await backend.release(reservation)

    assert global_reject == ExecutionFanoutDecision(False, 7, 3, "global")
    assert provider_reject == ExecutionFanoutDecision(False, 7, 3, "provider")
    assert admitted == ExecutionFanoutDecision(True, 2, 1, "")
    assert renewed is True
    assert RedisExecutionFanoutBackend._keys("abc") == (
        "{maestro-fanout}:global:expiry",
        "{maestro-fanout}:provider:abc:expiry",
    )
    assert len(redis.calls) == 5
    assert redis.calls[0][1] == 2
    assert redis.calls[0][2:4] == RedisExecutionFanoutBackend._keys("provider-key")
    assert redis.calls[0][4:7] == (100000, 110000, "lease")


@pytest.mark.asyncio
async def test_redis_backend_renew_false() -> None:
    redis = _FakeRedis([0])
    backend = RedisExecutionFanoutBackend(redis)
    reservation = ExecutionFanoutReservation("lease", "provider")
    assert await backend.renew(reservation, lease_seconds=5) is False


@pytest.mark.asyncio
async def test_heartbeat_raises_when_renew_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class Backend:
        async def renew(self, reservation, *, lease_seconds):
            return False

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(fanout_module.asyncio, "sleep", no_sleep)
    with pytest.raises(ExecutionFanoutLeaseLostError, match="lease lost"):
        await fanout_module._heartbeat(
            backend=Backend(),
            reservation=ExecutionFanoutReservation("lease", "provider"),
            lease_seconds=5,
        )


@pytest.mark.asyncio
async def test_heartbeat_treats_backend_exception_as_lease_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    class Backend:
        async def renew(self, reservation, *, lease_seconds):
            raise RuntimeError("redis down")

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(fanout_module.asyncio, "sleep", no_sleep)
    with pytest.raises(ExecutionFanoutLeaseLostError):
        await fanout_module._heartbeat(
            backend=Backend(),
            reservation=ExecutionFanoutReservation("lease", "provider"),
            lease_seconds=5,
        )


@pytest.mark.asyncio
async def test_run_with_execution_fanout_disabled_bypasses_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ExecutionFanoutPolicy,
        "from_env",
        classmethod(lambda cls: ExecutionFanoutPolicy(False, 1, 1, 5, 0, 5)),
    )
    called = 0

    async def operation() -> str:
        nonlocal called
        called += 1
        return "ok"

    assert await fanout_module.run_with_execution_fanout("OpenAI", operation) == "ok"
    assert called == 1


@pytest.mark.asyncio
async def test_run_with_execution_fanout_requires_shared_authority_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_redis():
        return None

    monkeypatch.setattr(fanout_module, "get_redis", no_redis)
    monkeypatch.setattr(fanout_module, "settings", SimpleNamespace(is_production=True))
    monkeypatch.setattr(
        ExecutionFanoutPolicy,
        "from_env",
        classmethod(lambda cls: ExecutionFanoutPolicy(True, 2, 2, 5, 0, 5)),
    )

    with pytest.raises(ExecutionFanoutAuthorityUnavailableError, match="authority"):
        await fanout_module.run_with_execution_fanout("provider", lambda: asyncio.sleep(0))


@pytest.mark.asyncio
async def test_run_with_execution_fanout_saturation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class Backend:
        async def reserve(self, **kwargs):
            return ExecutionFanoutDecision(False, 2, 1, "global")

        async def renew(self, reservation, *, lease_seconds):
            return True

        async def release(self, reservation):
            raise AssertionError("release should not be called before admission")

    async def no_redis():
        return None

    monkeypatch.setattr(fanout_module, "get_redis", no_redis)
    monkeypatch.setattr(fanout_module, "settings", SimpleNamespace(is_production=False))
    monkeypatch.setattr(fanout_module, "_LOCAL_BACKEND", Backend())
    monkeypatch.setattr(
        ExecutionFanoutPolicy,
        "from_env",
        classmethod(lambda cls: ExecutionFanoutPolicy(True, 2, 1, 5, 0, 5)),
    )

    with pytest.raises(ExecutionFanoutSaturatedError, match="global"):
        await fanout_module.run_with_execution_fanout("provider", lambda: asyncio.sleep(0))


@pytest.mark.asyncio
async def test_run_with_execution_fanout_local_success_releases(monkeypatch: pytest.MonkeyPatch) -> None:
    class Backend:
        def __init__(self) -> None:
            self.released = False
            self.reservation = None

        async def reserve(self, **kwargs):
            self.reservation = kwargs["reservation"]
            return ExecutionFanoutDecision(True, 1, 1)

        async def renew(self, reservation, *, lease_seconds):
            return True

        async def release(self, reservation):
            self.released = True
            assert reservation is self.reservation

    backend = Backend()

    async def no_redis():
        return None

    monkeypatch.setattr(fanout_module, "get_redis", no_redis)
    monkeypatch.setattr(fanout_module, "settings", SimpleNamespace(is_production=False))
    monkeypatch.setattr(fanout_module, "_LOCAL_BACKEND", backend)
    monkeypatch.setattr(
        ExecutionFanoutPolicy,
        "from_env",
        classmethod(lambda cls: ExecutionFanoutPolicy(True, 4, 2, 5, 0, 5)),
    )

    async def operation() -> str:
        return "result"

    assert await fanout_module.run_with_execution_fanout(" My Provider ", operation) == "result"
    assert backend.released is True
    assert backend.reservation.provider_key == fanout_module._provider_key("My Provider")


@pytest.mark.asyncio
async def test_run_with_execution_fanout_uses_redis_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = _FakeRedis([[1, 1, 1, 0], 1])

    async def get_fake_redis():
        return redis

    monkeypatch.setattr(fanout_module, "get_redis", get_fake_redis)
    monkeypatch.setattr(fanout_module, "settings", SimpleNamespace(is_production=True))
    monkeypatch.setattr(
        ExecutionFanoutPolicy,
        "from_env",
        classmethod(lambda cls: ExecutionFanoutPolicy(True, 3, 2, 5, 0, 5)),
    )

    assert await fanout_module.run_with_execution_fanout("provider", lambda: asyncio.sleep(0, result=9)) == 9
    assert len(redis.calls) == 2


def test_policy_action_mapping_known_and_unknown_values() -> None:
    assert map_to_governance_action("stable") is GovernanceAction.keep
    assert map_to_governance_action("repair_scaffold") is GovernanceAction.repair
    assert map_to_governance_action("extinct") is GovernanceAction.reject
    assert map_to_governance_action("unknown") is GovernanceAction.repair


def test_policy_engine_escalation_freeze_and_low_reward_priority() -> None:
    engine = PolicyEngine()

    escalated = engine.decide(
        "hybrid",
        0.4,
        "repair_scaffold",
        "Repair",
        PolicyContext(consecutive_failures=3),
    )
    frozen = engine.decide(
        "stable",
        0.8,
        "accept",
        "Accept",
        PolicyContext(consecutive_failures=5),
    )
    lowered = engine.decide(
        "stable",
        0.2,
        "accept",
        "Accept",
        PolicyContext(history_count=3, avg_reward=0.2),
    )

    assert escalated.action is GovernanceAction.escalate_to_human
    assert frozen.action is GovernanceAction.freeze_agent
    assert lowered.action is GovernanceAction.lower_priority
    assert "Human" in escalated.action_label
    assert "priority" in lowered.description.lower()


def test_policy_engine_distorted_and_extinct_override_base_mapping() -> None:
    engine = PolicyEngine()
    distorted = engine.decide("distorted", 0.1, "accept", "x")
    extinct = engine.decide("extinct", 0.0, "accept", "x")
    assert distorted.action is GovernanceAction.retry
    assert extinct.action is GovernanceAction.reject


def test_policy_engine_history_distribution_recent_and_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = PolicyEngine(max_history=2)
    timestamps = iter([10.0, 20.0, 30.0])
    monkeypatch.setattr("processual_api.cgt_governor.policy.engine.time.time", lambda: next(timestamps))

    keep = PolicyDecision(GovernanceAction.keep, "stable", 0.8, "accept", "Accept", "", "")
    repair = PolicyDecision(GovernanceAction.repair, "hybrid", 0.4, "repair_scaffold", "Repair", "", "")
    retry = PolicyDecision(GovernanceAction.retry, "distorted", 0.2, "restructure", "Retry", "", "")

    engine.record(keep, eval_id="one", reason="good")
    engine.record(repair, eval_id="two")
    last = engine.record(retry, eval_id="three", reason="bad")

    assert [r.eval_id for r in engine.history] == ["two", "three"]
    assert last.timestamp == 30.0
    assert last.reason == "bad"
    assert engine.action_distribution == {"repair": 1, "retry": 1}
    assert engine.recent(1) == [last]
    engine.clear_history()
    assert engine.history == []
    assert engine.action_distribution == {}


def _decision(rank: str) -> SanitizedPrivateDecision:
    return SanitizedPrivateDecision(
        existence_rank=f"rank:{rank}",
        dominant_constraint="constraint:public-safe",
        next_gate="gate:review",
        confidence_band="confidence:bounded",
        explanation_code="explanation:approved",
        policy_version="policy:v1",
    )


def test_legacy_govern_answer_fails_closed_without_private_boundary() -> None:
    with pytest.raises(PrivateEvaluationUnavailableError, match="private_evaluation_unavailable"):
        governor_module.govern_answer("answer", compatibility=0.9, coherence=0.8)


@pytest.mark.parametrize(
    ("rank", "policy", "repair_fragment"),
    [
        ("stable", "accept", None),
        ("hybrid", "repair_scaffold", "Preserve the correct core"),
        ("distorted", "restructure", "Rebuild from scratch"),
        ("transient", "deepen_or_clarify", "Deepen it without unnecessary length"),
    ],
)
def test_govern_sanitized_decision_routes_public_policy_and_repairs(
    rank: str,
    policy: str,
    repair_fragment: str | None,
) -> None:
    result = governor_module.govern_sanitized_decision(
        "answer",
        _decision(rank),
        language="en",
    )

    assert result.rank.value == rank
    assert result.policy == policy
    assert result.dominant_constraint == "constraint:public-safe"
    assert result.next_gate == "gate:review"
    assert result.confidence_band == "confidence:bounded"
    assert result.explanation_code == "explanation:approved"
    assert result.policy_version == "policy:v1"
    if repair_fragment is None:
        assert result.repair_prompt is None
    else:
        assert repair_fragment in result.repair_prompt
