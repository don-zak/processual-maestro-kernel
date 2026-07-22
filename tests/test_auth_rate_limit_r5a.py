from __future__ import annotations

import asyncio
from collections import defaultdict

import pytest

from processual_api.auth.rate_limit import (
    EMAIL_VERIFICATION_RESEND_RULES,
    EMAIL_VERIFICATION_RULES,
    ORGANIZATION_REGISTRATION_RULES,
    REGISTRATION_RULES,
    AuthRateLimitRule,
    AuthRateLimitUnavailableError,
    RedisAuthRateLimiter,
    TrustedProxyPolicy,
    resolve_client_ip,
)


class AtomicFakeRedis:
    def __init__(self) -> None:
        self.counts: defaultdict[str, int] = defaultdict(int)
        self.keys_seen: list[str] = []
        self._lock = asyncio.Lock()

    async def eval(self, script: str, numkeys: int, *values: object) -> list[int]:
        assert "redis.call('INCR', key)" in script
        keys = [str(value) for value in values[:numkeys]]
        arguments = [int(value) for value in values[numkeys:]]
        self.keys_seen.extend(keys)
        rejected = 0
        retry_ms = 0
        minimum_remaining: int | None = None
        async with self._lock:
            for index, key in enumerate(keys):
                limit = arguments[index * 2]
                window_ms = arguments[index * 2 + 1]
                self.counts[key] += 1
                current = self.counts[key]
                remaining = max(0, limit - current)
                minimum_remaining = remaining if minimum_remaining is None else min(minimum_remaining, remaining)
                if current > limit:
                    rejected = 1
                    retry_ms = max(retry_ms, window_ms)
        return [rejected, retry_ms, minimum_remaining or 0]


@pytest.mark.asyncio
async def test_concurrent_requests_cannot_exceed_atomic_limit() -> None:
    redis = AtomicFakeRedis()
    limiter = RedisAuthRateLimiter(redis, pepper=b"r" * 32)
    rule = (AuthRateLimitRule("burst", "ip", 5, 600),)

    decisions = await asyncio.gather(
        *(
            limiter.consume(
                action="register",
                subjects={"ip": "198.51.100.10"},
                rules=rule,
            )
            for _ in range(20)
        )
    )

    assert sum(decision.allowed for decision in decisions) == 5
    assert all(decision.retry_after_seconds == 600 for decision in decisions[5:])


@pytest.mark.asyncio
async def test_keys_are_hmac_only_and_rules_share_one_atomic_eval() -> None:
    redis = AtomicFakeRedis()
    limiter = RedisAuthRateLimiter(redis, pepper=b"p" * 32)
    subjects = {"ip": "203.0.113.4", "email": "private@example.com"}

    decision = await limiter.consume(
        action="register_individual",
        subjects=subjects,
        rules=REGISTRATION_RULES,
    )

    assert decision.allowed is True
    assert len(redis.keys_seen) == len(REGISTRATION_RULES)
    assert all(key.startswith("rl:auth:v1:register_individual:") for key in redis.keys_seen)
    serialized = " ".join(redis.keys_seen)
    assert subjects["ip"] not in serialized
    assert subjects["email"] not in serialized


@pytest.mark.asyncio
async def test_missing_subject_and_redis_failure_fail_closed() -> None:
    limiter = RedisAuthRateLimiter(AtomicFakeRedis(), pepper=b"x" * 32)
    with pytest.raises(ValueError, match="email"):
        await limiter.consume(
            action="register",
            subjects={"ip": "192.0.2.1"},
            rules=REGISTRATION_RULES,
        )

    class BrokenRedis:
        async def eval(self, script: str, numkeys: int, *values: object) -> object:
            raise ConnectionError("redis unavailable")

    unavailable = RedisAuthRateLimiter(BrokenRedis(), pepper=b"x" * 32)
    with pytest.raises(AuthRateLimitUnavailableError):
        await unavailable.consume(
            action="verify_email",
            subjects={"ip": "192.0.2.1", "token": "opaque-token"},
            rules=EMAIL_VERIFICATION_RULES,
        )


def test_security_policy_defaults_cover_registration_resend_and_verification() -> None:
    assert [(rule.dimension, rule.limit, rule.window_seconds) for rule in REGISTRATION_RULES] == [
        ("ip", 5, 600),
        ("ip", 20, 86400),
        ("email", 3, 86400),
    ]
    assert [(rule.dimension, rule.limit) for rule in ORGANIZATION_REGISTRATION_RULES] == [
        ("ip", 3),
        ("ip", 10),
        ("email", 3),
    ]
    assert [(rule.dimension, rule.limit) for rule in EMAIL_VERIFICATION_RESEND_RULES] == [
        ("ip", 10),
        ("email", 3),
        ("email", 5),
    ]
    assert [(rule.dimension, rule.limit) for rule in EMAIL_VERIFICATION_RULES] == [
        ("ip", 30),
        ("token", 5),
    ]


def test_untrusted_peer_cannot_spoof_forwarded_for() -> None:
    policy = TrustedProxyPolicy.from_cidrs(["10.0.0.0/8"])
    assert (
        resolve_client_ip(
            peer_ip="198.51.100.9",
            forwarded_for="1.2.3.4",
            policy=policy,
        )
        == "198.51.100.9"
    )


def test_trusted_proxy_chain_returns_first_untrusted_client_from_right() -> None:
    policy = TrustedProxyPolicy.from_cidrs(["10.0.0.0/8", "192.0.2.0/24"])
    assert (
        resolve_client_ip(
            peer_ip="10.0.0.10",
            forwarded_for="198.51.100.24, 192.0.2.12",
            policy=policy,
        )
        == "198.51.100.24"
    )


@pytest.mark.parametrize(
    "forwarded",
    ("not-an-ip", "198.51.100.1,,192.0.2.1", ",".join(["192.0.2.1"] * 9)),
)
def test_invalid_or_excessive_proxy_chain_falls_back_to_peer(forwarded: str) -> None:
    policy = TrustedProxyPolicy.from_cidrs(["10.0.0.0/8"])
    assert resolve_client_ip(peer_ip="10.0.0.8", forwarded_for=forwarded, policy=policy) == "10.0.0.8"


def test_rule_and_pepper_validation_reject_unsafe_configuration() -> None:
    with pytest.raises(ValueError):
        AuthRateLimitRule("invalid", "ip", 0, 60)
    with pytest.raises(ValueError, match="32 bytes"):
        RedisAuthRateLimiter(AtomicFakeRedis(), pepper=b"short")
    with pytest.raises(ValueError):
        TrustedProxyPolicy.from_cidrs(["10.0.0.0/8"], max_forwarded_hops=0)
