from __future__ import annotations

import hashlib
import hmac
import ipaddress
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

MINIMUM_PEPPER_BYTES = 32
DEFAULT_KEY_PREFIX = "rl:auth:v1"


class AsyncRedisRateLimitStore(Protocol):
    async def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object: ...


class AuthRateLimitUnavailableError(RuntimeError):
    """The authoritative Redis rate-limit decision could not be obtained."""


@dataclass(frozen=True, slots=True)
class AuthRateLimitRule:
    name: str
    dimension: str
    limit: int
    window_seconds: int

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.dimension.strip():
            raise ValueError("Rate-limit rule name and dimension are required.")
        if self.limit < 1 or self.window_seconds < 1:
            raise ValueError("Rate-limit rule limits and windows must be positive.")


@dataclass(frozen=True, slots=True)
class AuthRateLimitDecision:
    allowed: bool
    retry_after_seconds: int
    remaining: int


REGISTRATION_RULES = (
    AuthRateLimitRule("ip_burst", "ip", 5, 10 * 60),
    AuthRateLimitRule("ip_daily", "ip", 20, 24 * 60 * 60),
    AuthRateLimitRule("email_daily", "email", 3, 24 * 60 * 60),
)

ORGANIZATION_REGISTRATION_RULES = (
    AuthRateLimitRule("ip_hourly", "ip", 3, 60 * 60),
    AuthRateLimitRule("ip_daily", "ip", 10, 24 * 60 * 60),
    AuthRateLimitRule("email_daily", "email", 3, 24 * 60 * 60),
)

EMAIL_VERIFICATION_RESEND_RULES = (
    AuthRateLimitRule("ip_hourly", "ip", 10, 60 * 60),
    AuthRateLimitRule("email_hourly", "email", 3, 60 * 60),
    AuthRateLimitRule("email_daily", "email", 5, 24 * 60 * 60),
)

RECOVERY_EMAIL_ISSUE_RULES = (
    AuthRateLimitRule(
        "recovery_email_issue_ip",
        "ip",
        10,
        3600,
    ),
    AuthRateLimitRule(
        "recovery_email_issue_user",
        "user",
        5,
        3600,
    ),
)

RECOVERY_EMAIL_VERIFY_RULES = (
    AuthRateLimitRule(
        "recovery_email_verify_ip",
        "ip",
        30,
        3600,
    ),
    AuthRateLimitRule(
        "recovery_email_verify_token",
        "token",
        10,
        3600,
    ),
)


ACCOUNT_RECOVERY_START_RULES = (
    AuthRateLimitRule(
        "account_recovery_start_ip",
        "ip",
        10,
        3600,
    ),
    AuthRateLimitRule(
        "account_recovery_start_login",
        "login",
        5,
        3600,
    ),
)


ACCOUNT_RECOVERY_VERIFY_RULES = (
    AuthRateLimitRule(
        "account_recovery_verify_ip",
        "ip",
        30,
        3600,
    ),
    AuthRateLimitRule(
        "account_recovery_verify_token",
        "token",
        10,
        3600,
    ),
)


EMAIL_VERIFICATION_RULES = (
    AuthRateLimitRule("ip_window", "ip", 30, 15 * 60),
    AuthRateLimitRule("token_window", "token", 5, 15 * 60),
)

LOGIN_RULES = (
    AuthRateLimitRule("ip_window", "ip", 10, 15 * 60),
    AuthRateLimitRule("email_window", "email", 5, 15 * 60),
)

SESSION_REFRESH_RULES = (
    AuthRateLimitRule("ip_window", "ip", 60, 15 * 60),
    AuthRateLimitRule("token_window", "token", 10, 15 * 60),
)

MFA_VERIFICATION_RULES = (
    AuthRateLimitRule("ip_window", "ip", 20, 15 * 60),
    AuthRateLimitRule("user_window", "user", 8, 15 * 60),
)


_MULTI_WINDOW_SCRIPT = """
local rejected = 0
local max_retry_ms = 0
local min_remaining = nil

for index, key in ipairs(KEYS) do
    local limit = tonumber(ARGV[(index - 1) * 2 + 1])
    local window_ms = tonumber(ARGV[(index - 1) * 2 + 2])
    local current = redis.call('INCR', key)
    if current == 1 then
        redis.call('PEXPIRE', key, window_ms)
    end
    local ttl_ms = redis.call('PTTL', key)
    if ttl_ms < 0 then
        redis.call('PEXPIRE', key, window_ms)
        ttl_ms = window_ms
    end
    local remaining = limit - current
    if remaining < 0 then
        remaining = 0
    end
    if min_remaining == nil or remaining < min_remaining then
        min_remaining = remaining
    end
    if current > limit then
        rejected = 1
        if ttl_ms > max_retry_ms then
            max_retry_ms = ttl_ms
        end
    end
end

return {rejected, max_retry_ms, min_remaining or 0}
"""


class RedisAuthRateLimiter:
    def __init__(
        self,
        redis: AsyncRedisRateLimitStore,
        *,
        pepper: bytes,
        key_prefix: str = DEFAULT_KEY_PREFIX,
    ) -> None:
        if not isinstance(pepper, bytes) or len(pepper) < MINIMUM_PEPPER_BYTES:
            raise ValueError("Rate-limit pepper must contain at least 32 bytes.")
        if not key_prefix.strip():
            raise ValueError("Rate-limit key prefix must not be empty.")
        self._redis = redis
        self._pepper = pepper
        self._key_prefix = key_prefix.rstrip(":")

    def _key(self, *, action: str, rule: AuthRateLimitRule, value: str) -> str:
        material = f"pmk-auth-rate-limit-v1:{action}:{rule.dimension}:{value}".encode()
        digest = hmac.new(self._pepper, material, hashlib.sha256).hexdigest()
        return f"{self._key_prefix}:{action}:{rule.name}:{digest}"

    async def consume(
        self,
        *,
        action: str,
        subjects: Mapping[str, str],
        rules: Sequence[AuthRateLimitRule],
    ) -> AuthRateLimitDecision:
        if not action.strip() or not rules:
            raise ValueError("Rate-limit action and rules are required.")
        keys: list[str] = []
        arguments: list[int] = []
        for rule in rules:
            value = subjects.get(rule.dimension, "").strip()
            if not value:
                raise ValueError(f"Missing rate-limit subject: {rule.dimension}.")
            keys.append(self._key(action=action, rule=rule, value=value))
            arguments.extend((rule.limit, rule.window_seconds * 1000))
        try:
            result = await self._redis.eval(
                _MULTI_WINDOW_SCRIPT,
                len(keys),
                *keys,
                *arguments,
            )
        except Exception as exc:
            raise AuthRateLimitUnavailableError("Redis rate-limit authority is unavailable.") from exc
        if not isinstance(result, (list, tuple)) or len(result) != 3:
            raise AuthRateLimitUnavailableError("Redis returned an invalid rate-limit decision.")
        try:
            rejected, retry_ms, remaining = (int(value) for value in result)
        except (TypeError, ValueError) as exc:
            raise AuthRateLimitUnavailableError("Redis returned an invalid rate-limit decision.") from exc
        return AuthRateLimitDecision(
            allowed=rejected == 0,
            retry_after_seconds=max(0, math.ceil(retry_ms / 1000)),
            remaining=max(0, remaining),
        )


@dataclass(frozen=True, slots=True)
class TrustedProxyPolicy:
    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()
    max_forwarded_hops: int = 8

    @classmethod
    def from_cidrs(
        cls,
        cidrs: Sequence[str],
        *,
        max_forwarded_hops: int = 8,
    ) -> TrustedProxyPolicy:
        if max_forwarded_hops < 1:
            raise ValueError("max_forwarded_hops must be positive.")
        return cls(
            networks=tuple(ipaddress.ip_network(value.strip(), strict=False) for value in cidrs),
            max_forwarded_hops=max_forwarded_hops,
        )

    def is_trusted(self, value: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
        return any(value in network for network in self.networks)


def resolve_client_ip(
    *,
    peer_ip: str,
    forwarded_for: str | None,
    policy: TrustedProxyPolicy,
) -> str:
    peer = ipaddress.ip_address(peer_ip.strip())
    if not policy.is_trusted(peer) or not forwarded_for:
        return peer.compressed
    raw_hops = [part.strip() for part in forwarded_for.split(",")]
    if not raw_hops or len(raw_hops) > policy.max_forwarded_hops or any(not part for part in raw_hops):
        return peer.compressed
    try:
        hops = [ipaddress.ip_address(part) for part in raw_hops]
    except ValueError:
        return peer.compressed
    for candidate in reversed([*hops, peer]):
        if not policy.is_trusted(candidate):
            return candidate.compressed
    return hops[0].compressed


__all__ = [
    "ACCOUNT_RECOVERY_START_RULES",
    "ACCOUNT_RECOVERY_VERIFY_RULES",
    "EMAIL_VERIFICATION_RESEND_RULES",
    "EMAIL_VERIFICATION_RULES",
    "LOGIN_RULES",
    "MFA_VERIFICATION_RULES",
    "ORGANIZATION_REGISTRATION_RULES",
    "RECOVERY_EMAIL_ISSUE_RULES",
    "RECOVERY_EMAIL_VERIFY_RULES",
    "REGISTRATION_RULES",
    "SESSION_REFRESH_RULES",
    "AuthRateLimitDecision",
    "AuthRateLimitRule",
    "AuthRateLimitUnavailableError",
    "RedisAuthRateLimiter",
    "TrustedProxyPolicy",
    "resolve_client_ip",
]
