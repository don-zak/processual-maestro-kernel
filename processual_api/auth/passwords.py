from __future__ import annotations

from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type


@dataclass(frozen=True, slots=True)
class PasswordHashPolicy:
    time_cost: int = 3
    memory_cost_kib: int = 65_536
    parallelism: int = 4
    hash_len: int = 32
    salt_len: int = 16

    def __post_init__(self) -> None:
        if self.time_cost < 3:
            raise ValueError("Argon2id time_cost must be at least 3.")
        if self.memory_cost_kib < 65_536:
            raise ValueError("Argon2id memory cost must be at least 64 MiB.")
        if self.parallelism < 1:
            raise ValueError("Argon2id parallelism must be positive.")
        if self.hash_len < 32 or self.salt_len < 16:
            raise ValueError("Argon2id hash and salt lengths are too short.")


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    valid: bool
    needs_rehash: bool = False


class PasswordService:
    def __init__(self, policy: PasswordHashPolicy | None = None) -> None:
        self.policy = policy or PasswordHashPolicy()
        self._hasher = PasswordHasher(
            time_cost=self.policy.time_cost,
            memory_cost=self.policy.memory_cost_kib,
            parallelism=self.policy.parallelism,
            hash_len=self.policy.hash_len,
            salt_len=self.policy.salt_len,
            type=Type.ID,
        )

    def hash_password(self, password: str) -> str:
        if not isinstance(password, str) or not password:
            raise ValueError("password must be a non-empty string.")
        encoded = self._hasher.hash(password)
        if not encoded.startswith("$argon2id$"):
            raise RuntimeError("Password backend did not produce Argon2id.")
        return encoded

    def verify_password(self, encoded_hash: str, password: str) -> PasswordVerification:
        if not isinstance(encoded_hash, str) or not isinstance(password, str):
            return PasswordVerification(valid=False)
        try:
            valid = self._hasher.verify(encoded_hash, password)
        except InvalidHashError, VerificationError, VerifyMismatchError:
            return PasswordVerification(valid=False)
        if not valid:
            return PasswordVerification(valid=False)
        return PasswordVerification(
            valid=True,
            needs_rehash=self._hasher.check_needs_rehash(encoded_hash),
        )


__all__ = ["PasswordHashPolicy", "PasswordService", "PasswordVerification"]
